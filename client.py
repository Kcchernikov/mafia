import grpc
import sys
from colorama import init
init()
from colorama import Fore, Style
from art import tprint
from simple_term_menu import TerminalMenu
import random

sys.path.append("./proto/")
import mafia_pb2
import mafia_pb2_grpc

players_quorum = 4

class Client:
    def __init__(self):
        self.name = ""
        self.room = -1
        self.error_cnt = 0
        self.players = {}
        self.sheriff_result = ""
        self.role = mafia_pb2.Role.CITIZEN

    def start(self):
        print(Fore.GREEN + Style.BRIGHT)
        tprint("Mafia    online")
        print(Fore.WHITE + Style.BRIGHT)
        print("Добро пожаловать в клиент игры \"Мафия\"\n")
        channel, stub = self.connect()
        self.choose_room(stub)
        menu = TerminalMenu(['Играть самому', 'Сыграйте за меня'])
        ans = menu.show()
        print(Fore.WHITE + Style.BRIGHT)
        auto_play = (ans == 1)
        self.set_name(stub)
        self.wait_start(stub)
        self.play_game(stub, auto_play)

    def process_fail_status(self, response):
        print(Fore.RED + Style.BRIGHT)
        print("Сервер вернул следующую ошибу:", response.message)
        print(Fore.WHITE + Style.BRIGHT)

    def process_rpc_error(self, rpc_error, message="Ошибка подключения к серверу"):
        print(Fore.RED + Style.BRIGHT)
        print(message)
        print("Подробнее об ошибке: ", end='')
        if rpc_error.code() == grpc.StatusCode.CANCELLED:
            print('CANCELLED')
        elif rpc_error.code() == grpc.StatusCode.UNAVAILABLE:
            print('UNAVAILABLE')
        else:
            print(f"Received unknown RPC error: code={rpc_error.code()} message={rpc_error.details()}")
        self.error_cnt += 1
        if self.error_cnt >= 100:
            print("Слишком много ошибок, возможно потеряно соединение с сервером, перезапустите клиент")
        print(Fore.WHITE + Style.BRIGHT)


    def connect(self):
        connected = False
        while connected == False:
            print("Для подключания к серверу введите адрес в формате \'0.0.0.0:9000\': ", end = '')
            address = input()
            if len(address) == 0:
                print("Вы ввели пустой адресс, вместо него будет подставлен \'0.0.0.0:9000\'")
                address = '0.0.0.0:9000'
            channel = grpc.insecure_channel(address)
            stub = mafia_pb2_grpc.MafiaStub(channel)
            query = mafia_pb2.Request(message = "Connect")
            try:
                response = stub.Connect(query)
                if response.status == mafia_pb2.Status.FAIL:
                    self.process_fail_status(response)
                else:
                    print("Вы успешно подключились!")
                    connected = True
            except grpc.RpcError as rpc_error:
                self.process_rpc_error(rpc_error, message="Ошибка подключения к серверу, перепроверьте адресс и попробуйте снова")
        return channel, stub

    def choose_room(self, stub):
        success = False
        while success == False:
            print("Выберите подходящий для вас вариант", end = '')
            print(Fore.WHITE + Style.BRIGHT)
            menu = TerminalMenu(['Создать комнату', 'Подключиться к любой существующей комнате', 'Подключится к комнате по номеру'])
            ans = menu.show()
            print(Fore.WHITE + Style.BRIGHT)
            number = -2
            if ans == 1:
                number = -1
            elif ans == 2:
                print("Введите номер комнаты: ", end='')
                try:
                    number = int(input())
                    if number < 0:
                        print(Fore.RED + Style.BRIGHT)
                        print("Номер комнаты не может быть отрицательным")
                        print(Fore.WHITE + Style.BRIGHT)
                        continue
                except:
                    print(Fore.RED + Style.BRIGHT)
                    print("Не удается распознать номер комнаты, удостоверьтесь, что вы ввели все правильно")
                    print(Fore.WHITE + Style.BRIGHT)
                    continue
            try:
                query = mafia_pb2.ChooseRoomRequest(room = number)
            except:
                print(Fore.RED + Style.BRIGHT)
                print("Некорректный номер комнаты")
                print(Fore.WHITE + Style.BRIGHT)
                continue

            try:
                response = stub.ChooseRoom(query)
                if response.status == mafia_pb2.Status.FAIL:
                    self.process_fail_status(response)
                else:
                    print(response.message)
                    success = True
            except grpc.RpcError as rpc_error:
                self.process_rpc_error(rpc_error)

    def set_name(self, stub):
        success = False
        while success == False:
            print("Введите ваше имя, его будут видеть другие игроки: ", end = '')
            name = input()
            query = mafia_pb2.Request(message = name)
            try:
                response = stub.SetName(query)
                if response.status == mafia_pb2.Status.FAIL:
                    self.process_fail_status(response)
                else:
                    print("Вы успешно установили имя \'", name, "\'", sep='')
                    self.name = name
                    success = True
            except grpc.RpcError as rpc_error:
                self.process_rpc_error(rpc_error)

    def wait_start(self, stub):
        print()
        print("Ожидание игроков\n")
        players_in_room = {self.name}
        print("В комнате сейчас находятся следующие игроки:", ', '.join(f"'{w}'" for w in list(players_in_room)))
        print(f"Также в комнате еще 0 игроков выбирают имя")
        while len(players_in_room) < players_quorum and self.error_cnt < 100:
            query = mafia_pb2.Request(message = self.name)
            try:
                for member_response in stub.WaitStart(query):
                    if member_response.response.status == mafia_pb2.Status.FAIL:
                        self.process_fail_status(member_response.response)
                    else:
                        if len(member_response.connected) != 0:
                            players_in_room.add(member_response.connected)

                        print('\033[F\033[K', end='')
                        print('\033[F\033[K', end='')
                        print("В комнате сейчас находятся следующие игроки:", ', '.join(f"'{w}'" for w in sorted(list(players_in_room))))
                        print(f"Также в комнате еще {member_response.unnamed} игроков выбирают имя")
            except grpc.RpcError as rpc_error:
                self.process_rpc_error(rpc_error)

    def day_choose(self, stub, response, is_auto = False):
        print(f"\nНачался день номер {response.day}")
        print("Живы игроки:", ', '.join(f"'{w}'" for w in sorted(list(response.alive))))
        self.players = sorted(list(response.alive))
        is_alive = True
        if not self.name in list(response.alive):
            is_alive = False
            print("Вы мерты и наблюдаете за игрой")
        if is_alive:
            ans = -1
            published = False
            voted = False
            while ans != 0:
                opts = ['Завершить день']
                if response.day > 1:
                    opts.append('Казнить игрока')
                if self.role == mafia_pb2.Role.SHERIFF and len(self.sheriff_result) > 0 and published == False:
                    opts.append('Опубликовать данные')
                if is_auto == True:
                    ans = random.randint(0, len(opts) - 1)
                    if voted == True and ans == 1:
                        ans = 0
                    elif ans == 1:
                        voted = True
                else:
                    menu = TerminalMenu(opts)
                    ans = menu.show()
                print(Fore.WHITE + Style.BRIGHT)
                if ans == 0:
                    try:
                        res = stub.SetReady(mafia_pb2.Request(message = self.name))
                        if res.status == mafia_pb2.Status.FAIL:
                            self.process_fail_status(res)
                    except grpc.RpcError as rpc_error:
                        self.process_rpc_error(rpc_error)
                elif ans == 1:
                    name = ""
                    if self.name in self.players:
                        pl = set(self.players)
                        pl.discard(self.name)
                        name = random.choice(list(pl))
                    else:
                        name = random.choice(self.players)
                    if is_auto == False:
                        print("Введите имя игрока: ", end = '')
                        name = input()
                    try:
                        res = stub.Vote(mafia_pb2.Request(message = name))
                        if res.status == mafia_pb2.Status.FAIL:
                            self.process_fail_status(res)
                        else:
                            print(res.message)
                    except grpc.RpcError as rpc_error:
                        self.process_rpc_error(rpc_error)
                elif ans == 2:
                    try:
                        res = stub.PublishData(mafia_pb2.Request(message = self.sheriff_result))
                        if res.status == mafia_pb2.Status.FAIL:
                            self.process_fail_status(res)
                        else:
                            print("Вы успешно опубликовали данные")
                            published = True
                    except grpc.RpcError as rpc_error:
                        self.process_rpc_error(rpc_error)
                else:
                    break

    def play_game(self, stub, is_auto = False):
        print()
        alive = players_quorum
        self.players = {}
        print(f"Игра началась. Учавствуют {alive} игроков\n")
        query = mafia_pb2.Request(message = self.name)
        self.sheriff_result = ""
        self.role = mafia_pb2.Role.CITIZEN
        try:
            for response in stub.GameProcess(query):
                if response.response.status == mafia_pb2.Status.FAIL:
                    self.process_fail_status(response.response)
                else:
                    if response.message == "Role":
                        print("Ваша роль: ", end = '')
                        self.role = response.role
                        if self.role == mafia_pb2.Role.CITIZEN:
                            print("Мирный житель")
                        elif self.role == mafia_pb2.Role.MAFIA:
                            print("Мафия")
                        else:
                            print("Комиссар")
                    elif response.message == "Day":
                        self.day_choose(stub, response, is_auto)
                    elif response.message == "Night":
                        print(f"\nНачалась ночь")
                        print("Живы игроки:", ', '.join(f"'{w}'" for w in sorted(list(response.alive))))
                        is_alive = True
                        if not self.name in list(response.alive):
                            is_alive = False
                        if is_alive:
                            success = False
                            while success == False:
                                if self.role == mafia_pb2.Role.MAFIA:
                                    name = ""
                                    if self.name in self.players:
                                        pl = set(self.players)
                                        pl.discard(self.name)
                                        name = random.choice(list(pl))
                                    else:
                                        name = random.choice(self.players)
                                    if is_auto == False:
                                        print("Вы мафия, введите имя игрока, которого хотите убить: ", end = '')
                                        name = input()
                                    try:
                                        res = stub.Kill(mafia_pb2.Request(message = name))
                                        if res.status == mafia_pb2.Status.FAIL:
                                            self.process_fail_status(res)
                                        else:
                                            print(res.message)
                                            success = True
                                    except grpc.RpcError as rpc_error:
                                        self.process_rpc_error(rpc_error)
                                elif self.role == mafia_pb2.Role.SHERIFF:
                                    name = ""
                                    if self.name in self.players:
                                        pl = set(self.players)
                                        pl.discard(self.name)
                                        name = random.choice(list(pl))
                                    else:
                                        name = random.choice(self.players)
                                    if is_auto == False:
                                        print("Вы комиссар, введите имя игрока, которого хотите проверить: ", end = '')
                                        name = input()
                                    try:
                                        res = stub.Check(mafia_pb2.Request(message = name))
                                        if res.status == mafia_pb2.Status.FAIL:
                                            self.process_fail_status(res)
                                        else:
                                            if res.message == "True":
                                                print(f"Вы успешно проверили игрока '{name}', он мафия!")
                                                self.sheriff_result = name
                                            else:
                                                print(f"Вы успешно проверили игрока '{name}', он не мафия!")
                                            success = True
                                    except grpc.RpcError as rpc_error:
                                        self.process_rpc_error(rpc_error)
                                else:
                                    success = True

                    elif response.message == "Info":
                        if response.info.action == mafia_pb2.Action.VOTE:
                            print(f"Игрок '{response.info.send}' проголосовал за '{response.info.receive}'")
                        elif response.info.action == mafia_pb2.Action.KILL:
                            print(f"Мафия убила игрока {response.info.receive}")
                        elif response.info.action == mafia_pb2.Action.PUBLISH_DATA:
                            print(f"Комиссар нашел мафию, это оказался игрок '{response.info.receive}'")
                    elif response.message == "VoteResult":
                        print(f"В результате голосования был выбран игрок '{response.response.message}'")
                        alive -= 1
                    elif response.message == "End":
                        if response.winner == mafia_pb2.Role.MAFIA:
                            print(f"Игра завершена, победила мафия")
                        else:
                            print(f"Игра завершена, победили мирные жители")

        except grpc.RpcError as rpc_error:
            self.process_rpc_error(rpc_error)


if __name__ == "__main__":
    client = Client()
    client.start()