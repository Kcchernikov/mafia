from concurrent import futures
import grpc
import sys

sys.path.append("./proto/")
import mafia_pb2
import mafia_pb2_grpc

import asyncio
import random
import pika

players_quorum = 4
time_async_sleep = 0.5

class Player:
    def __init__(self):
        self.name = ""
        self.room = -1
    
class Room:
    def __init__(self, members):
        self.members = members
        self.is_started = False
        self.roles = dict()
        self.day = 0
        self.alive = {}         # names
        self.votes = dict()
        self.ready = 0
        self.mafia_vote = 0
        self.sheriff_vote = 0
        self.is_dead_sheriff = False
        self.published = False
        self.is_night = False

class EService(mafia_pb2_grpc.MafiaServicer):
    def __init__(self):
        self.rooms = []
        self.players = dict()
        self.conntection_params = pika.ConnectionParameters(host='rabbitmq', port=5672,
            heartbeat=60000, blocked_connection_timeout=30000)
        self.connection = pika.BlockingConnection(self.conntection_params)
        self.channels = list()

    async def Connect(self, request, context):
        print("Received 'Connect' !", flush=True)
        if context.peer() in self.players:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Игрок с данным адрессом уже есть на сервере"
            )
        self.players[context.peer()] = Player()
        print("Connected", context.peer(), flush=True)
        return mafia_pb2.Response(
            status = mafia_pb2.Status.SUCCESS,
            message = "Успешное подключение"
        )
    
    async def ChooseRoom(self, request, context):
        print("Received 'ChooseRoom' !", flush=True)
        if not context.peer() in self.players:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Игрока с данным адрессом нет на сервере, переподключитесь, чтобы выбрать комнату"
            )
        message = "Успешный выбор комнаты. "
        if request.room == -2:
            self.players[context.peer()].room = len(self.rooms)
            self.rooms.append(Room({context.peer()}))
            if not self.connection or self.connection.is_closed:
                self.connection = pika.BlockingConnection(self.conntection_params)
            num = len(self.channels)
            self.channels.append(self.connection.channel())
            self.channels[num].exchange_declare(exchange=str(self.players[context.peer()].room), exchange_type='fanout')
        elif request.room == -1:
            found = False
            for i in range(len(self.rooms)):
                if len(self.rooms[i].members) < players_quorum and self.rooms[i].is_started == False:
                    self.rooms[i].members.add(context.peer())
                    self.players[context.peer()].room = i
                    found = True
                    break
            if found == False:
                self.players[context.peer()].room = len(self.rooms)
                self.rooms.append(Room({context.peer()}))
                num = len(self.channels)
                if not self.connection or self.connection.is_closed:
                    self.connection = pika.BlockingConnection(self.conntection_params)
                self.channels.append(self.connection.channel())
                self.channels[num].exchange_declare(exchange=str(self.players[context.peer()].room), exchange_type='fanout')
        elif (request.room >= len(self.rooms)
                or len(self.rooms[request.room].members) >= players_quorum 
                or self.rooms[request.room].is_started == True):
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Такой комнаты не существует, либо она уже заполена"
            )
        elif self.players[context.peer()].room == -1:
            self.players[context.peer()].room = request.room
            self.rooms[request.room].members.add(context.peer())
        else:
            if self.players[context.peer()].room != request.room:
                self.rooms[self.players[context.peer()].room].members.discard(context.peer())
                self.rooms[request.room].members.add(context.peer())
                self.players[context.peer()].room = request.room
                message = "Успешная смена комнаты. "
            else:
                return mafia_pb2.Response(
                    status = mafia_pb2.Status.FAIL,
                    message="Нельзя поменять комнату на туже самую"
                )
        message += "Теперь вы находитесь в комнате номер " + str(self.players[context.peer()].room)
        return mafia_pb2.Response(status = mafia_pb2.Status.SUCCESS, message=message, room = self.players[context.peer()].room)
    
    async def SetName(self, request, context):
        print("Received 'SetName' !", flush=True)
        if not context.peer() in self.players:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Игрока с данным адрессом нет на сервере, переподключитесь, чтобы установить имя"
            )
        if request.message == "Server":
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Имя 'Server' зарезервированно"
            )
        message = "Успешная установка имени"
        if self.players[context.peer()].room < 0:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Выберите комнату прежде, чем выбирать имя"
            )
        elif self.players[context.peer()].room >= len(self.rooms):
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Вашей комнаты не существует, выберете существующую комнату прежде чем устанавливать имя"
            )
        else:
            for pl in self.rooms[self.players[context.peer()].room].members:
                if self.players[pl].name == request.message:
                    return mafia_pb2.Response(
                        status = mafia_pb2.Status.FAIL,
                        message="В вашей комнате уже есть игрок с данным именем, выберите другое"
                    )

        if len(self.players[context.peer()].name) == 0:
            self.players[context.peer()].name = request.message
        else:
            if self.players[context.peer()].name != request.messafe:
                self.players[context.peer()].name = request.message
                message = "Успешная смена имени"
            else:
                return mafia_pb2.Response(
                    status = mafia_pb2.Status.FAIL,
                    message="Нельзя поменять имя на тоже самое"
                )
        return mafia_pb2.Response(status = mafia_pb2.Status.SUCCESS, message=message)
    
    async def WaitStart(self, request, context):
        print("Received 'WaitStart' !", flush=True)
        if not context.peer() in self.players:
            yield mafia_pb2.MemberResponse(response = mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Игрока с данным адрессом нет на сервере, переподключитесь, чтобы установить имя"
            ))
            return
        room_id = self.players[context.peer()].room
        if room_id < 0 or room_id > len(self.rooms):
            yield mafia_pb2.MemberResponse(response = mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Некорректный номер комнаты"
            ))
            return
        players_cnt = len(self.rooms[room_id].members)
        sended_cnt = 1
        sended = {context.peer()}
        unnamed = 0
        cur_unnamed = 0
        while players_cnt - unnamed < players_quorum or sended_cnt < players_cnt:
            players_cnt = len(self.rooms[room_id].members)
            for pl in self.rooms[room_id].members:
                if (not pl in sended) and len(self.players[pl].name) > 0:
                    sended_cnt += 1
                    sended.add(pl)
                    unnamed = 0
                    for pl1 in self.rooms[room_id].members:
                        if len(self.players[pl1].name) == 0:
                            unnamed += 1
                    cur_unnamed = unnamed
                    yield mafia_pb2.MemberResponse(
                        response = mafia_pb2.Response(status = mafia_pb2.Status.SUCCESS),
                        unnamed = unnamed,
                        connected = self.players[pl].name
                    )

            unnamed = 0
            for pl in self.rooms[room_id].members:
                if len(self.players[pl].name) == 0:
                    unnamed += 1
            if cur_unnamed != unnamed:
                cur_unnamed = unnamed
                yield mafia_pb2.MemberResponse(
                    response = mafia_pb2.Response(status = mafia_pb2.Status.SUCCESS),
                    unnamed = unnamed,
                    connected = ""
                )
            await asyncio.sleep(time_async_sleep)

    async def Vote(self, request, context):
        print("Received 'Vote' !", flush=True)
        if not context.peer() in self.players:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Игрока с данным адрессом нет на сервере, переподключитесь, чтобы установить имя"
            )
        room_id = self.players[context.peer()].room
        if room_id < 0 or room_id > len(self.rooms):
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Некорректный номер комнаты"
            )
        if not self.players[context.peer()].name in self.rooms[room_id].alive:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Вы дух и не можете голосовать"
            )
        if self.players[context.peer()].name == request.message:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Нельзя голосовать за себя"
            )
        found = False
        vote = -1
        for member in self.rooms[room_id].members:
            if self.players[member].name == request.message:
                if not self.players[member].name in self.rooms[room_id].alive:
                    return mafia_pb2.Response(
                        status = mafia_pb2.Status.FAIL,
                        message="В вашей комнате нет живых игроков с таким именем"
                    )
                else:
                    vote = member
                    found = True
                    break

        if found == False:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="В вашей комнате нет живых игроков с таким именем"
            )
        
        if context.peer() in self.rooms[room_id].votes and vote == self.rooms[room_id].votes[context.peer()]:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Вы уже проголосовали за этого игрока"
            )
        
        change = True
        if (not context.peer() in self.rooms[room_id].votes) or self.rooms[room_id].votes[context.peer()] == 0:
            change = False

        self.rooms[room_id].votes[context.peer()] = vote

        if change == True:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.SUCCESS,
                message = f"Вы успешно поменяли свой голос на {request.message}"
            )
        else:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.SUCCESS,
                message = f"Вы успешно проголосовали за {request.message}"
            )

    async def SetReady(self, request, context):
        print("Received 'SetReady' !", flush=True)
        if not context.peer() in self.players:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Игрока с данным адрессом нет на сервере, переподключитесь, чтобы установить имя"
            )
        room_id = self.players[context.peer()].room
        if room_id < 0 or room_id > len(self.rooms):
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Некорректный номер комнаты"
            )
        self.rooms[room_id].ready += 1
        return mafia_pb2.Response(
            status = mafia_pb2.Status.SUCCESS,
            message = "Успешно"
        )
    
    async def Kill(self, request, context):
        print("Received 'Kill' !", flush=True)
        if not context.peer() in self.players:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Игрока с данным адрессом нет на сервере, переподключитесь, чтобы установить имя"
            )
        room_id = self.players[context.peer()].room
        if room_id < 0 or room_id > len(self.rooms):
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Некорректный номер комнаты"
            )
        if self.rooms[room_id].roles[context.peer()] != mafia_pb2.Role.MAFIA:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Только мафия может убивать"
            )
        if not request.message in self.rooms[room_id].alive:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Среди живых нет такого игрока"
            )
        if request.message == self.players[context.peer()].name:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Нельзя убивать себя"
            )
        if not self.players[context.peer()].name in self.rooms[room_id].alive:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Вы дух и не можете убивать"
            )
        self.rooms[room_id].mafia_vote = request.message
        return mafia_pb2.Response(
            status = mafia_pb2.Status.SUCCESS,
            message = f"Вы успешно убили {request.message}"
        )
    
    async def Check(self, request, context):
        print("Received 'Check' !", flush=True)
        if not context.peer() in self.players:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Игрока с данным адрессом нет на сервере, переподключитесь, чтобы установить имя"
            )
        room_id = self.players[context.peer()].room
        if room_id < 0 or room_id > len(self.rooms):
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Некорректный номер комнаты"
            )
        if self.rooms[room_id].roles[context.peer()] != mafia_pb2.Role.SHERIFF:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Только шериф может проверять"
            )
        if not request.message in self.rooms[room_id].alive:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Среди живых нет такого игрока"
            )
        if request.message == self.players[context.peer()].name:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Нельзя проверять себя"
            )
        if not self.players[context.peer()].name in self.rooms[room_id].alive:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Вы дух и не можете проверять"
            )
        self.rooms[room_id].sheriff_vote = request.message
        message = "False"
        for pl in self.rooms[room_id].members:
            if self.players[pl].name == request.message:
                if self.rooms[room_id].roles[pl] == mafia_pb2.Role.MAFIA:
                    message = "True"
                break
        return mafia_pb2.Response(
            status = mafia_pb2.Status.SUCCESS,
            message = message
        )
    
    async def PublishData(self, request, context):
        print("Received 'PublishData' !", flush=True)
        if not context.peer() in self.players:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Игрока с данным адрессом нет на сервере, переподключитесь, чтобы установить имя"
            )
        room_id = self.players[context.peer()].room
        if room_id < 0 or room_id > len(self.rooms):
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Некорректный номер комнаты"
            )
        if self.rooms[room_id].roles[context.peer()] != mafia_pb2.Role.SHERIFF:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Только шериф может публиковать данные"
            )
        if request.message == self.players[context.peer()].name:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Нельзя проверять себя"
            )
        
        if self.rooms[room_id].published == True:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Вы уже опубликовали данные"
            )
        if not self.players[context.peer()].name in self.rooms[room_id].alive:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Вы дух и не можете публиковать данные"
            )
        self.rooms[room_id].published = True
        self.channels[room_id].basic_publish(
            exchange=str(room_id),
            routing_key='',
            body = str(f"Server -> Комиссар нашел мафию, это оказался игрок '{self.rooms[room_id].sheriff_vote}'")
        )
        return mafia_pb2.Response(
            status = mafia_pb2.Status.SUCCESS,
            message = "Успешно"
        )
    
    async def SendMessage(self, request, context):
        print("Received 'SendMessage' !", flush=True)
        if not context.peer() in self.players:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Игрока с данным адрессом нет на сервере, переподключитесь, чтобы установить имя"
            )
        room_id = self.players[context.peer()].room
        if room_id < 0 or room_id > len(self.rooms):
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Некорректный номер комнаты"
            )
        if not self.players[context.peer()].name in self.rooms[room_id].alive:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Вы дух и не можете отправлять данные"
            )
        if self.rooms[room_id].is_night:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Ночью сообщения запрещены"
            )
        self.channels[room_id].basic_publish(
            exchange=str(room_id),
            routing_key='',
            body = str(self.players[context.peer()].name + " -> " + request.message)
        )
        return mafia_pb2.Response(
            status = mafia_pb2.Status.SUCCESS,
            message = "Успешно"
        )
    
    async def GameProcess(self, request, context):
        print("Received 'GameProcess' !", flush=True)
        if not context.peer() in self.players:
            yield mafia_pb2.GameResponse(response = mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Игрока с данным адрессом нет на сервере, переподключитесь, чтобы установить имя"
            ))
            return
        room_id = self.players[context.peer()].room
        if room_id < 0 or room_id > len(self.rooms):
            yield mafia_pb2.GameResponse(response = mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Некорректный номер комнаты"
            ))
            return
        if len(self.rooms[room_id].members) < players_quorum:
            yield mafia_pb2.GameResponse(response = mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message=f"Для начала игры должно быть минимум {players_quorum} человека"
            ))
            return
        if self.rooms[room_id].day > 1:
            yield mafia_pb2.GameResponse(response = mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Игра уже началась"
            ))
            return

        self.rooms[room_id].is_started = True
        if len(self.rooms[room_id].roles) == 0:
            roles = [mafia_pb2.Role.MAFIA, mafia_pb2.Role.SHERIFF, mafia_pb2.Role.CITIZEN, mafia_pb2.Role.CITIZEN]
            random.shuffle(roles)
            i = 0
            for pl in self.rooms[room_id].members:
                self.rooms[room_id].roles[pl] = roles[i]
                i += 1
            self.rooms[room_id].day = 1
            alive = {self.players[context.peer()].name}
            for pl in self.rooms[room_id].members:
                alive.add(self.players[pl].name)
            self.rooms[room_id].alive = alive
            self.rooms[room_id].ready = 0
            self.rooms[room_id].votes = dict()

        yield mafia_pb2.GameResponse(
            response = mafia_pb2.Response(status = mafia_pb2.Status.SUCCESS),
            message="Role",
            role = self.rooms[room_id].roles[context.peer()]
        )
        alive = self.rooms[room_id].alive
        votes = dict()
        is_finished = False
        published = False
        day = 1

        while is_finished == False:
            wait = len(self.rooms[room_id].alive)
            yield mafia_pb2.GameResponse(
                response = mafia_pb2.Response(status = mafia_pb2.Status.SUCCESS),
                message="Day",
                day = self.rooms[room_id].day,
                alive = self.rooms[room_id].alive
            )
            published = False
            ready = 0
            while ready < wait and day >= self.rooms[room_id].day:
                ready = self.rooms[room_id].ready
                for vote in self.rooms[room_id].votes:
                    message = ""
                    if not vote in votes:
                        message = "проголосовал"
                    elif self.rooms[room_id].votes[vote] != votes[vote]:
                        message = "изменил голос и проголосовал за"
                    if len(message) != 0:
                        votes[vote] = self.rooms[room_id].votes[vote]
                        yield mafia_pb2.GameResponse(
                            response = mafia_pb2.Response(
                                status = mafia_pb2.Status.SUCCESS,
                                message = message
                            ),
                            message="Info",
                            day = self.rooms[room_id].day,
                            alive = self.rooms[room_id].alive,
                            info = mafia_pb2.Info(
                                action = mafia_pb2.Action.VOTE,
                                send = self.players[vote].name,
                                receive = self.players[votes[vote]].name
                            )
                        )
                if self.rooms[room_id].published == True and published == False:
                    published = True
                    yield mafia_pb2.GameResponse(
                        response = mafia_pb2.Response(status = mafia_pb2.Status.SUCCESS),
                        message="Info",
                        day = self.rooms[room_id].day,
                        alive = self.rooms[room_id].alive,
                        info = mafia_pb2.Info(
                            action = mafia_pb2.Action.PUBLISH_DATA,
                            receive = self.rooms[room_id].sheriff_vote
                        )
                    )
                await asyncio.sleep(time_async_sleep)

            if day != 1:
                voted = self.rooms[room_id].votes
                voted = dict()
                for vote in votes:
                    if not votes[vote] in voted:
                        voted[votes[vote]] = 1
                    else:
                        voted[votes[vote]] += 1
                if len(votes) > 0:
                    killed = max(voted, key=voted.get)
                    self.rooms[room_id].alive.discard(self.players[killed].name)
                    yield mafia_pb2.GameResponse(
                        response = mafia_pb2.Response(
                            status = mafia_pb2.Status.SUCCESS,
                            message = self.players[killed].name
                        ),
                        message="VoteResult",
                        day = self.rooms[room_id].day,
                        alive = self.rooms[room_id].alive,
                    )
                    winner = mafia_pb2.Role.MAFIA
                    if self.rooms[room_id].roles[killed] == mafia_pb2.Role.MAFIA:
                        is_finished = True
                        winner = mafia_pb2.Role.CITIZEN
                    elif len(self.rooms[room_id].alive) <= 2:
                        is_finished = True
                    elif self.rooms[room_id].roles[killed] == mafia_pb2.Role.SHERIFF:
                        self.rooms[room_id].is_dead_sheriff = True
                    if is_finished:
                        yield mafia_pb2.GameResponse(
                            response = mafia_pb2.Response(status = mafia_pb2.Status.SUCCESS),
                            message="End",
                            day = self.rooms[room_id].day,
                            alive = self.rooms[room_id].alive,
                            winner = winner
                        )
            day += 1
            votes = dict()
            if day != self.rooms[room_id].day:
                self.rooms[room_id].day = day
                self.rooms[room_id].ready = 0
                self.rooms[room_id].votes = dict()
                self.rooms[room_id].mafia_vote = 0
                self.rooms[room_id].sheriff_vote = 0
                self.rooms[room_id].published = False

            if is_finished:
                continue
            
            yield mafia_pb2.GameResponse(
                response = mafia_pb2.Response(status = mafia_pb2.Status.SUCCESS),
                message="Night",
                day = self.rooms[room_id].day,
                alive = self.rooms[room_id].alive
            )
            self.rooms[room_id].is_night = True

            while ((self.rooms[room_id].mafia_vote == 0) or 
                (self.rooms[room_id].sheriff_vote == 0 and self.rooms[room_id].is_dead_sheriff == False)):
                await asyncio.sleep(time_async_sleep)

            
            if self.rooms[room_id].mafia_vote != 0:
                self.rooms[room_id].alive.discard(self.rooms[room_id].mafia_vote)
                for pl in self.rooms[room_id].members:
                    if self.players[pl].name == self.rooms[room_id].mafia_vote:
                        if self.rooms[room_id].roles[pl] == mafia_pb2.Role.SHERIFF:
                            self.rooms[room_id].is_dead_sheriff = True

                yield mafia_pb2.GameResponse(
                    response = mafia_pb2.Response(status = mafia_pb2.Status.SUCCESS),
                    message="Info",
                    day = self.rooms[room_id].day,
                    alive = self.rooms[room_id].alive,
                    info = mafia_pb2.Info(
                        action = mafia_pb2.Action.KILL,
                        receive = self.rooms[room_id].mafia_vote
                    )
                )
                if len(self.rooms[room_id].alive) <= 2:
                    is_finished = True
                    yield mafia_pb2.GameResponse(
                        response = mafia_pb2.Response(status = mafia_pb2.Status.SUCCESS),
                        message="End",
                        day = self.rooms[room_id].day,
                        alive = self.rooms[room_id].alive,
                        winner = mafia_pb2.Role.MAFIA
                    )
            self.rooms[room_id].is_night = False

            
async def serve():
    server = grpc.aio.server()
    mafia_pb2_grpc.add_MafiaServicer_to_server(EService(),server)
    server.add_insecure_port('[::]:9000')
    await server.start()
    print("Server started. Awaiting jobs...", flush=True)
    await server.wait_for_termination()

if __name__ == '__main__':
    asyncio.run(serve())