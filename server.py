from concurrent import futures
import pickle
import grpc
import time
import sys

sys.path.append("./proto/")
import mafia_pb2
import mafia_pb2_grpc

import asyncio

class Player:
    def __init__(self):
        self.name = ""
        self.room = -1

class EService(mafia_pb2_grpc.MafiaServicer):
    def __init__(self):
        self.rooms = []
        self.players = dict()

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
            self.rooms.append({context.peer()})
        elif request.room == -1:
            found = False
            for i in range(len(self.rooms)):
                if len(self.rooms[i]) < 4:
                    self.rooms[i].add(context.peer())
                    self.players[context.peer()].room = i
                    found = True
                    break
            if found == False:
                self.players[context.peer()].room = len(self.rooms)
                self.rooms.append({context.peer()})
        elif request.room >= len(self.rooms) or len(self.rooms[request.room]) >= 4:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Такой комнаты не существует"
            )
        elif self.players[context.peer()].room == -1:
            self.players[context.peer()].room = request.room
            self.rooms[request.room].add(context.peer())
        else:
            if self.players[context.peer()].room != request.room:
                self.rooms[self.players[context.peer()].room].discard(context.peer())
                self.rooms[request.room].add(context.peer())
                self.players[context.peer()].room = request.room
                message = "Успешная смена комнаты. "
            else:
                return mafia_pb2.Response(
                    status = mafia_pb2.Status.FAIL,
                    message="Нельзя поменять комнату на туже самую"
                )
        message += "Теперь вы находитесь в комнате номер " + str(self.players[context.peer()].room)
        return mafia_pb2.Response(status = mafia_pb2.Status.SUCCESS, message=message)
    
    async def SetName(self, request, context):
        print("Received 'SetName' !", flush=True)
        if not context.peer() in self.players:
            return mafia_pb2.Response(
                status = mafia_pb2.Status.FAIL,
                message="Игрока с данным адрессом нет на сервере, переподключитесь, чтобы установить имя"
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
            for pl in self.rooms[self.players[context.peer()].room]:
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
        players_cnt = len(self.rooms[room_id])
        sended_cnt = 1
        sended = {context.peer()}
        unnamed = 0
        cur_unnamed = 0
        while players_cnt - unnamed < 4 or sended_cnt < players_cnt:
            players_cnt = len(self.rooms[room_id])
            # print(request.message + ":", players_cnt, self.rooms[room_id], sended, flush=True)
            for pl in self.rooms[room_id]:
                # print(request.message + ":", self.players[pl].name)
                if (not pl in sended) and len(self.players[pl].name) > 0:
                    sended_cnt += 1
                    sended.add(pl)
                    unnamed = 0
                    for pl1 in self.rooms[room_id]:
                        if len(self.players[pl1].name) == 0:
                            unnamed += 1
                    cur_unnamed = unnamed
                    yield mafia_pb2.MemberResponse(
                        response = mafia_pb2.Response(status = mafia_pb2.Status.SUCCESS),
                        unnamed = unnamed,
                        connected = self.players[pl].name
                    )

            unnamed = 0
            for pl in self.rooms[room_id]:
                if len(self.players[pl].name) == 0:
                    unnamed += 1
            if cur_unnamed != unnamed:
                cur_unnamed = unnamed
                yield mafia_pb2.MemberResponse(
                    response = mafia_pb2.Response(status = mafia_pb2.Status.SUCCESS),
                    unnamed = unnamed,
                    connected = ""
                )
            await asyncio.sleep(1)
            
async def serve():
    server = grpc.aio.server()
    mafia_pb2_grpc.add_MafiaServicer_to_server(EService(),server)
    server.add_insecure_port('[::]:9000')
    await server.start()
    print("Server started. Awaiting jobs...", flush=True)
    await server.wait_for_termination()

if __name__ == '__main__':
    asyncio.run(serve())