import grpc
import sys
from colorama import init
init()
from colorama import Fore, Style
from art import tprint
from simple_term_menu import TerminalMenu

sys.path.append("./proto/")
import mafia_pb2
import mafia_pb2_grpc

class Client:
    def __init__(self):
        self.name = ""
        self.room = -1
        self.error_cnt = 0

    def start(self):
        print(Fore.GREEN + Style.BRIGHT)
        tprint("Mafia    online")
        print(Fore.WHITE + Style.BRIGHT)
        print("Добро пожаловать в клиент игры \"Мафия\"\n")
        channel, stub = self.connect()
        self.choose_room(stub)
        self.set_name(stub)
        self.wait_start(stub)

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
        print("В комнате сейчас находятся следующие игроки:", ', '.join(list(players_in_room)))
        print(f"Также в комнате еще 0 игроков выбирают имя")
        while len(players_in_room) < 4 and self.error_cnt < 100:
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
                        print("В комнате сейчас находятся следующие игроки:", ', '.join(sorted(list(players_in_room))))
                        print(f"Также в комнате еще {member_response.unnamed} игроков выбирают имя")
            except grpc.RpcError as rpc_error:
                self.process_rpc_error(rpc_error)


if __name__ == "__main__":
    client = Client()
    client.start()