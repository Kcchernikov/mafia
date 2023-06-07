import grpc
import sys
import os
from colorama import init
init()
from colorama import Fore, Style
from art import tprint
from simple_term_menu import TerminalMenu
import random
import pika
from threading import Thread
from threading import Lock
from tkinter import *

sys.path.append("./proto/")
import mafia_pb2
import mafia_pb2_grpc

players_quorum = 4

BG_GRAY = "#ABB2B9"
BG_GREEN = "#00FF00"
BG_COLOR = "#17202A"
TEXT_COLOR = "#EAECEE"

FONT = "Helvetica 14"
FONT_BOLD = "Helvetica 13 bold"

os.environ["TK_SILENCE_DEPRECATION"] = "1"

class Client:
    def __init__(self):
        self.name = ""
        self.room = -1
        self.error_cnt = 0
        self.players = {}
        self.sheriff_result = ""
        self.role = mafia_pb2.Role.CITIZEN
        self.game_finished = False
        self.auto_play = False
        self.stub = 0
        self.txt = 0
        self.e = 0
        self.host = '0.0.0.0'
        self.window = 0
        self.lock = Lock()

    def start(self):
        self.window = Tk()
        self.window.title("MAFIA GAME")
        self.window.resizable(False, False)

        self.lable = Label(self.window, bg=BG_COLOR, fg=TEXT_COLOR, text="MAFIA GAME", font=FONT_BOLD, pady=10, width=20, height=1)
        self.lable.grid(row=0, column=0, columnspan=2)
        self.con = Button(self.window, text="Connect", font="Helvetica 18", bg="green",
              command=self.connect, height = 20, width = 40)
        self.con.grid(row=1, column=0,columnspan=2, padx = 40)
        self.window.mainloop()

    def receive_from_chat(self):
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=self.host, port=5672, heartbeat=60000, blocked_connection_timeout=30000)
            )
            channel = connection.channel()
            channel.exchange_declare(exchange=str(self.room), exchange_type='fanout')

            result = channel.queue_declare(queue='', exclusive=True)
            queue_name = result.method.queue

            channel.queue_bind(exchange=str(self.room), queue=queue_name)

            def callback(ch, method, properties, body):
                self.chat_txt.configure(state=NORMAL)
                self.chat_txt.insert(END, "\n" + body.decode())
                self.chat_txt.configure(state=DISABLED)

            channel.basic_consume(
                queue=queue_name, on_message_callback=callback, auto_ack=True)
            
            channel.start_consuming()
        except:
            print("pika BlockingConnection Error, close client")
            exit(0)

    def send_to_chat(self):
        res = self.stub.SendMessage(mafia_pb2.Request(message = self.e_chat.get()))
        if res.status == mafia_pb2.Status.FAIL:
            self.process_fail_status(res)
        self.e_chat.delete(0, END)

    def write_to_game(self, txt):
        self.game_txt.configure(state=NORMAL)
        self.game_txt.insert(END, "\n" + txt)
        self.game_txt.configure(state=DISABLED)

    def process_fail_status(self, response):
        # print(Fore.RED + Style.BRIGHT)
        self.write_to_game("Сервер вернул следующую ошибу: " + response.message)
        # print(Fore.WHITE + Style.BRIGHT)

    def process_rpc_error(self, rpc_error, message="Ошибка подключения к серверу"):
        # self.write_to_game(Fore.RED + Style.BRIGHT)
        self.write_to_game(message)
        self.write_to_game("Подробнее об ошибке: ")
        if rpc_error.code() == grpc.StatusCode.CANCELLED:
            self.write_to_game('CANCELLED')
        elif rpc_error.code() == grpc.StatusCode.UNAVAILABLE:
            self.write_to_game('UNAVAILABLE')
        else:
            self.write_to_game(f"Received unknown RPC error: code={rpc_error.code()} message={rpc_error.details()}")
        self.error_cnt += 1
        if self.error_cnt >= 100:
            self.write_to_game("Слишком много ошибок, возможно потеряно соединение с сервером, перезапустите клиент")
        # self.write_to_game(Fore.WHITE + Style.BRIGHT)


    def connect(self):
        self.con.grid_remove()
        self.con.destroy()
        self.game_txt = Text(self.window, bg=BG_COLOR, fg=TEXT_COLOR, font=FONT, width=80, state=DISABLED)
        self.game_txt.grid(row=1, column=0, columnspan=3, rowspan=1)
        self.game_txt.tag_configure("red", foreground="red")
        def try_connect():
            address = self.e_game.get()
            self.write_to_game("You -> " + address)
            self.e_game.delete(0, END)
            if len(address) == 0:
                self.write_to_game("Вы ввели пустой адресс, вместо него будет подставлен \'0.0.0.0:9000\'")
                address = '0.0.0.0:9000'
            channel = grpc.insecure_channel(address)
            self.stub = mafia_pb2_grpc.MafiaStub(channel)
            query = mafia_pb2.Request(message = "Connect")
            try:
                response = self.stub.Connect(query)
                if response.status == mafia_pb2.Status.FAIL:
                    self.process_fail_status(response)
                else:
                    self.host = address.split(":")[0]
                    self.write_to_game("Вы успешно подключились!")
                    self.choose_room()
            except grpc.RpcError as rpc_error:
                self.process_rpc_error(rpc_error, message="Ошибка подключения к серверу, перепроверьте адресс и попробуйте снова")
                self.write_to_game("Для подключания к серверу введите адрес в формате \'0.0.0.0:9000\': ")

        self.e_game = Entry(self.window, bg="#2C3E50", fg=TEXT_COLOR, font=FONT, width=70)
        self.e_game.grid(row=2, column=0, columnspan=1)
        self.send_game = Button(self.window, text="Send", font=FONT_BOLD, bg=BG_GRAY,
              command=try_connect)
        self.send_game.grid(row=2, column=1,columnspan=1, sticky="e")
        self.write_to_game("Для подключания к серверу введите адрес в формате \'0.0.0.0:9000\': ")

    def choose_room(self):
        self.e_game.grid_remove()
        self.send_game.grid_remove()
        self.lable.grid(row=0, column=1, columnspan=1)
        def choose(num):
            try:
                query = mafia_pb2.ChooseRoomRequest(room = num)
            except:
                # print(Fore.RED + Style.BRIGHT)
                self.write_to_game("Некорректный номер комнаты")
                return
                # print(Fore.WHITE + Style.BRIGHT)
            try:
                response = self.stub.ChooseRoom(query)
                if response.status == mafia_pb2.Status.FAIL:
                    self.process_fail_status(response)
                else:
                    self.write_to_game(response.message)
                    self.room = response.room
                    self.lable.grid(row=0, column=0, columnspan=2)
                    if num < 0:
                        self.create.grid_remove()
                        self.exist.grid_remove()
                        self.number.grid_remove()
                        self.e_game.grid()
                    else:
                        self.send_noom.grid_remove()
                    self.set_name()
            except grpc.RpcError as rpc_error:
                self.process_rpc_error(rpc_error)
        def on_create():
            choose(-2)
        def on_exist():
            choose(-1)
        def on_number():
            self.create.grid_remove()
            self.exist.grid_remove()
            self.number.grid_remove()
            self.lable.grid(row=0, column=0, columnspan=2)
            self.e_game.grid()
            def read_num():
                num = self.e_game.get()
                self.write_to_game("You -> " + num)
                self.e_game.delete(0, END)
                try:
                    number = int(num)
                    if number < 0:
                        # print(Fore.RED + Style.BRIGHT)
                        self.write_to_game("Номер комнаты не может быть отрицательным")
                        # print(Fore.WHITE + Style.BRIGHT)
                    else:
                        choose(number)
                except:
                    # print(Fore.RED + Style.BRIGHT)
                    self.write_to_game("Не удается распознать номер комнаты, удостоверьтесь, что вы ввели все правильно")
                    # print(Fore.WHITE + Style.BRIGHT)
                    
            self.send_noom = Button(self.window, text="Send", font=FONT_BOLD, bg=BG_GRAY,
                command=read_num)
            self.send_noom.grid(row=2, column=1, columnspan=1, sticky="e")

        self.create = Button(self.window, text="Создать комнату", font="Helvetica 13", bg="green",
              command=on_create, height = 5, width = 18)
        self.create.grid(row=2, column=0,columnspan=1, padx = 0, pady=10)
        self.exist = Button(self.window, text="Подключиться к любой\n существующей комнате", font="Helvetica 13", bg="green",
              command=on_exist, height = 5, width = 18)
        self.exist.grid(row=2, column=1,columnspan=1, padx = 0, pady=10)
        self.number = Button(self.window, text="Подключится к комнате\n по номеру", font="Helvetica 13", bg="green",
              command=on_number, height = 5, width = 18)
        self.number.grid(row=2, column=2,columnspan=1, padx = 0, pady=10)

    def set_name(self):
        self.write_to_game("Введите ваше имя, его будут видеть другие игроки: ")
        def on_name():
            name = self.e_game.get()
            self.write_to_game("You -> " + name)
            self.e_game.delete(0, END)
            query = mafia_pb2.Request(message = name)
            try:
                response = self.stub.SetName(query)
                if response.status == mafia_pb2.Status.FAIL:
                    self.process_fail_status(response)
                else:
                    self.write_to_game("Вы успешно установили имя \'" + name + "\'")
                    self.name = name
                    self.choose_auto_play()
            except grpc.RpcError as rpc_error:
                self.process_rpc_error(rpc_error)
        self.send_game = Button(self.window, text="Send", font=FONT_BOLD, bg=BG_GRAY,
            command=on_name)
        self.send_game.grid(row=2, column=1,columnspan=1, sticky="e")
    def choose_auto_play(self):
        self.send_game.grid_remove()
        self.e_game.grid_remove()
        self.lable.grid(row=0, column=1, columnspan=2)
        self.game_txt.grid(row=1, column=0, columnspan=4, rowspan=1)
        def on_self_play():
            self.auto_play = False
            self.self_play.grid_remove()
            self.auto_play_b.grid_remove()
            self.lable.grid(row=0, column=1, columnspan=1)
            self.game_txt.grid(row=1, column=0, columnspan=3, rowspan=1)
            self.wait_start()
        def on_auto_play():
            self.auto_play = True
            self.self_play.grid_remove()
            self.auto_play_b.grid_remove()
            self.lable.grid(row=0, column=1, columnspan=1)
            self.game_txt.grid(row=1, column=0, columnspan=3, rowspan=1)
            self.wait_start()
        self.self_play = Button(self.window, text="Играть самому", font="Helvetica 13", bg="green",
              command=on_self_play, height = 5, width = 18)
        self.self_play.grid(row=2, column=0,columnspan=2, padx = 0, pady=10)
        self.auto_play_b = Button(self.window, text="Сыграйте за меня", font="Helvetica 13", bg="green",
              command=on_auto_play, height = 5, width = 18)
        self.auto_play_b.grid(row=2, column=2,columnspan=2, padx = 0, pady=10)

    def wait_start(self):
        players_in_room = {self.name}
        self.write_to_game("\nОжидание игроков\n")
        self.write_to_game("В комнате сейчас находятся следующие игроки: " + ', '.join(f"'{w}'" for w in list(players_in_room)))
        self.write_to_game("Также в комнате еще 0 игроков выбирают имя")
        def wait():
            players_in_room = {self.name}
            while len(players_in_room) < players_quorum and self.error_cnt < 100:
                query = mafia_pb2.Request(message = self.name)
                try:
                    for member_response in self.stub.WaitStart(query):
                        if member_response.response.status == mafia_pb2.Status.FAIL:
                            self.process_fail_status(member_response.response)
                        else:
                            if len(member_response.connected) != 0:
                                players_in_room.add(member_response.connected)
                            self.game_txt.configure(state=NORMAL)
                            self.game_txt.delete("end-2l","end")
                            self.game_txt.configure(state=DISABLED)
                            self.write_to_game("В комнате сейчас находятся следующие игроки: " + ', '.join(f"'{w}'" for w in sorted(list(players_in_room))))
                            self.write_to_game(f"Также в комнате еще {member_response.unnamed} игроков выбирают имя")
                except grpc.RpcError as rpc_error:
                    self.process_rpc_error(rpc_error)
            self.play_game()
        self.t_game = Thread(target=wait, args=[])
        self.t_game.start()  

    def day_choose(self, response):
        self.write_to_game(f"\nНачался день номер {response.day}")
        self.write_to_game("Живы игроки: " + ', '.join(f"'{w}'" for w in sorted(list(response.alive))))
        self.players = sorted(list(response.alive))
        def on_end_day():
            try:
                res = self.stub.SetReady(mafia_pb2.Request(message = self.name))
                if res.status == mafia_pb2.Status.FAIL:
                    self.process_fail_status(res)
                else:
                    if not is_auto:
                        self.end_day.grid_remove()
                        self.vote_person.grid_remove()
                        self.publish_data.grid_remove()
                    self.day_status = 0
            except grpc.RpcError as rpc_error:
                self.write_to_game("on_end_day_error")
                self.process_rpc_error(rpc_error)

        def on_vote_person():
            self.day_status = 1
            name = ""
            if self.name in self.players:
                pl = set(self.players)
                pl.discard(self.name)
                name = random.choice(list(pl))
            else:
                name = random.choice(self.players)

            def vote(name, is_auto):
                try:
                    res = self.stub.Vote(mafia_pb2.Request(message = name))
                    if res.status == mafia_pb2.Status.FAIL:
                        self.process_fail_status(res)
                    else:
                        self.write_to_game(res.message)
                        if not is_auto:
                            self.lable.grid(row=0, column=0, columnspan=2)
                            self.send_vote.grid_remove()
                            self.e_game.grid_remove()
                            self.end_day.grid()
                            self.vote_person.grid()
                            self.publish_data.grid()
                            if self.published:
                                self.publish_data.configure(state=DISABLED)

                except grpc.RpcError as rpc_error:
                    self.process_rpc_error(rpc_error)

            if is_auto == False:
                self.write_to_game("Введите имя игрока: ")
                self.end_day.grid_remove()
                self.vote_person.grid_remove()
                self.publish_data.grid_remove()
                self.lable.grid(row=0, column=0, columnspan=2)
                self.e_game.grid()
                def read_vote():
                    name = self.e_game.get()
                    self.write_to_game("You -> " + name)
                    self.e_game.delete(0, END)
                    vote(name, False)
                    
                self.send_vote = Button(self.window, text="Send", font=FONT_BOLD, bg=BG_GRAY,
                    command=read_vote)
                self.send_vote.grid(row=2, column=1, columnspan=1, sticky="e")
            else:
                vote(name, True)

        def on_publish_data():
            self.day_status = 2
            try:
                res = self.stub.PublishData(mafia_pb2.Request(message = self.sheriff_result))
                if res.status == mafia_pb2.Status.FAIL:
                    self.process_fail_status(res)
                else:
                    self.write_to_game("Вы успешно опубликовали данные")
                    self.publish_data.configure(state=DISABLED)
                    self.published = True
                    self.publish_data.configure(state=DISABLED)

            except grpc.RpcError as rpc_error:
                self.process_rpc_error(rpc_error)
        is_auto = self.auto_play
        is_alive = True
        if not self.name in list(response.alive):
            is_alive = False
            self.write_to_game("Вы мерты и наблюдаете за игрой")
            if not is_auto:
                self.e_chat.configure(state=DISABLED)
                self.send_chat.configure(state=DISABLED)
        if is_alive:
            if not is_auto:
                self.e_chat.configure(state=NORMAL)
                self.send_chat.configure(state=NORMAL)
            self.day_status = -1
            self.published = False
            voted = False
            self.end_day = Button(self.window, text="Завершить день", font="Helvetica 13", bg="green",
                command=on_end_day, height = 2, width = 18)
            self.vote_person = Button(self.window, text="Казнить игрока", font="Helvetica 13", bg="green",
                command=on_vote_person, height = 2, width = 18)
            self.publish_data = Button(self.window, text="Опубликовать данные", font="Helvetica 13", bg="green",
                command=on_publish_data, height = 2, width = 18)
            if not is_auto:

                self.end_day.grid(row=2, column=0,columnspan=1, padx = 0, pady=10)
                self.vote_person.grid(row=2, column=1,columnspan=1, padx = 0, pady=10)
                self.vote_person.configure(state=DISABLED)
                self.publish_data.grid(row=2, column=2,columnspan=1, padx = 0, pady=10)
                self.publish_data.configure(state=DISABLED)

            while self.day_status != 0:
                if self.published:
                    self.publish_data.configure(state=DISABLED)
                opts = ['Завершить день']
                if response.day > 1:
                    if not is_auto:
                        self.vote_person.configure(state=NORMAL)
                    opts.append('Казнить игрока')
                if self.role == mafia_pb2.Role.SHERIFF and len(self.sheriff_result) > 0 and self.published == False:
                    if not is_auto:
                        self.publish_data.configure(state=NORMAL)
                    opts.append('Опубликовать данные')
                if is_auto == True:
                    ans = random.randint(0, len(opts) - 1)
                    if voted == True and ans == 1:
                        ans = 0
                    elif ans == 1:
                        voted = True
                    if ans == 0:
                        on_end_day()
                    elif ans == 1:
                        on_vote_person()
                    elif ans == 2:
                        on_publish_data

    def play_game(self):
        is_auto = self.auto_play
        if not is_auto:
            self.lable.grid(row=0, column=1, columnspan=1)
            self.game_txt.grid(row=1, column=0, columnspan=3, rowspan=1)
            self.chat_lable = Label(self.window, bg=BG_COLOR, fg=TEXT_COLOR, text="CHAT", font=FONT_BOLD, pady=10, width=20, height=1)
            self.chat_lable.grid(row=0, column=3, columnspan=2)
            self.chat_txt = Text(self.window, bg=BG_COLOR, fg=TEXT_COLOR, font=FONT, width=60)
            self.chat_txt.grid(row=1, column=3, columnspan=2, rowspan=1)
            self.chat_txt.configure(state=DISABLED)
    
            self.e_chat = Entry(self.window, bg="#2C3E50", fg=TEXT_COLOR, font=FONT, width=50)
            self.e_chat.grid(row=2, column=3, columnspan=1)

            self.send_chat = Button(self.window, text="Send", font=FONT_BOLD, bg=BG_GRAY,
                  command=self.send_to_chat)
            self.send_chat.grid(row=2, column=4,columnspan=1, sticky="e")

            self.t_receive = Thread(target=self.receive_from_chat, args=[])
            self.t_receive.start()
 
        alive = players_quorum
        self.players = {}
        self.write_to_game(f"\nИгра началась. Учавствуют {alive} игроков\n")
        query = mafia_pb2.Request(message = self.name)
        self.sheriff_result = ""
        self.role = mafia_pb2.Role.CITIZEN
        try:
            for response in self.stub.GameProcess(query):
                if response.response.status == mafia_pb2.Status.FAIL:
                    self.process_fail_status(response.response)
                else:
                    if response.message == "Role":
                        self.write_to_game("Ваша роль: ")
                        self.role = response.role
                        if self.role == mafia_pb2.Role.CITIZEN:
                            self.write_to_game("Мирный житель")
                        elif self.role == mafia_pb2.Role.MAFIA:
                            self.write_to_game("Мафия")
                        else:
                            self.write_to_game("Комиссар")
                    elif response.message == "Day":
                        self.day_choose(response)
                    elif response.message == "Night":
                        if not is_auto:
                            self.e_chat.configure(state=DISABLED)
                            self.send_chat.configure(state=DISABLED)
                        self.write_to_game(f"\nНачалась ночь")
                        self.write_to_game("Живы игроки: " + ', '.join(f"'{w}'" for w in sorted(list(response.alive))))
                        is_alive = True
                        if not self.name in list(response.alive):
                            is_alive = False
                        if is_alive:
                            if self.role == mafia_pb2.Role.MAFIA:
                                name = ""
                                if self.name in self.players:
                                    pl = set(self.players)
                                    pl.discard(self.name)
                                    name = random.choice(list(pl))
                                else:
                                    name = random.choice(self.players)
                                def kill(name, is_auto):
                                    try:
                                        res = self.stub.Kill(mafia_pb2.Request(message = name))
                                        if res.status == mafia_pb2.Status.FAIL:
                                            self.process_fail_status(res)
                                        else:
                                            self.write_to_game(res.message)
                                            if not is_auto:
                                                self.send_kill.grid_remove()
                                                self.e_game.grid_remove()

                                    except grpc.RpcError as rpc_error:
                                        self.process_rpc_error(rpc_error)

                                def on_kill():
                                    name = self.e_game.get()
                                    self.write_to_game("You -> " + name)
                                    self.e_game.delete(0, END)
                                    kill(name, False)
                                
                                if is_auto == False:
                                    self.lable.grid(row=0, column=0, columnspan=2)
                                    self.e_game.grid()
                                        
                                    self.send_kill = Button(self.window, text="Send", font=FONT_BOLD, bg=BG_GRAY,
                                        command=on_kill)
                                    self.send_kill.grid(row=2, column=1, columnspan=1, sticky="e")
                                
                                    self.write_to_game("Вы мафия, введите имя игрока, которого хотите убить: ")
                                else:
                                    kill(name, True)
                            elif self.role == mafia_pb2.Role.SHERIFF:
                                name = ""
                                if self.name in self.players:
                                    pl = set(self.players)
                                    pl.discard(self.name)
                                    name = random.choice(list(pl))
                                else:
                                    name = random.choice(self.players)
                                def check(name, is_auto):
                                    try:
                                        res = self.stub.Check(mafia_pb2.Request(message = name))
                                        if res.status == mafia_pb2.Status.FAIL:
                                            self.process_fail_status(res)
                                        else:
                                            if res.message == "True":
                                                self.write_to_game(f"Вы успешно проверили игрока '{name}', он мафия!")
                                                self.sheriff_result = name
                                            else:
                                                self.write_to_game(f"Вы успешно проверили игрока '{name}', он не мафия!")
                                            if not is_auto:
                                                self.send_check.grid_remove()
                                                self.e_game.grid_remove()

                                    except grpc.RpcError as rpc_error:
                                        self.process_rpc_error(rpc_error)

                                def on_check():
                                    name = self.e_game.get()
                                    self.write_to_game("You -> " + name)
                                    self.e_game.delete(0, END)
                                    check(name, False)
                                
                                if is_auto == False:
                                    self.lable.grid(row=0, column=0, columnspan=2)
                                    self.e_game.grid()
                                        
                                    self.send_check = Button(self.window, text="Send", font=FONT_BOLD, bg=BG_GRAY,
                                        command=on_check)
                                    self.send_check.grid(row=2, column=1, columnspan=1, sticky="e")
                                
                                    self.write_to_game("Вы комиссар, введите имя игрока, которого хотите проверить: ")
                                else:
                                    check(name, True)

                    elif response.message == "Info":
                        if response.info.action == mafia_pb2.Action.VOTE:
                            self.write_to_game(f"Игрок '{response.info.send}' проголосовал за '{response.info.receive}'")
                        elif response.info.action == mafia_pb2.Action.KILL:
                            self.write_to_game(f"Мафия убила игрока {response.info.receive}")
                        elif response.info.action == mafia_pb2.Action.PUBLISH_DATA:
                            self.write_to_game(f"Комиссар нашел мафию, это оказался игрок '{response.info.receive}'")
                    elif response.message == "VoteResult":
                        self.write_to_game(f"В результате голосования был выбран игрок '{response.response.message}'")
                        alive -= 1
                    elif response.message == "End":
                        if not is_auto:
                            self.e_chat.configure(state=NORMAL)
                            self.send_chat.configure(state=NORMAL)
                        if response.winner == mafia_pb2.Role.MAFIA:
                            self.write_to_game(f"Игра завершена, победила мафия")
                        else:
                            self.write_to_game(f"Игра завершена, победили мирные жители")

        except grpc.RpcError as rpc_error:
            self.process_rpc_error(rpc_error)


if __name__ == "__main__":
    client = Client()
    client.start()