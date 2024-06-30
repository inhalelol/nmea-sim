import socket
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import struct
import math


def ddmm_to_decimal(degrees_minutes):
    degrees = int(degrees_minutes // 100)
    minutes = degrees_minutes % 100
    return degrees + minutes / 60


def decimal_to_ddmm(decimal_degrees):
    degrees = int(decimal_degrees)
    minutes = (decimal_degrees - degrees) * 60
    return degrees * 100 + minutes


def add_cyclic(a, b, max_value=359):
    result = (a + b) % (max_value + 1)
    return result


class UdpServer:
    """
    Listen data from PLC

    Attributes:
        host (str): Host to listen
        port (int): Port to listen
    """

    def __init__(self, host: str = '127.0.0.1', port: int = 25565):

        self.sock = None

        try:
            # Создание UDP сокета
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            # Привязка сокета к указанному адресу и порту
            server_address = (host, port)
            self.sock.bind(server_address)

        except OSError as e:
            print(f"Error: {e}")
        print(f'Server listening on {host}:{port}')

    def rec_data(self) -> bytes:
        data, address = self.sock.recvfrom(100)  # 4096 - максимальный размер буфера
        print(f'Received {len(data)} bytes from {address}')
        return data

    def send_bytes(self, data: bytes, ip: str = '127.0.0.1', port: int = 25565):
        self.sock.sendto(data, (ip, port))
        print(f'Send {data} to {ip} on {port}')


class NmeaSentence(ABC):

    def __init__(self):
        self.data = None

    @abstractmethod
    def upd_data(self, data: list):
        """

        """
        pass

    def calculate_checksum(self, message: bytes) -> str:
        """

        """
        checksum = 0
        for byte in message[1:]:
            checksum ^= byte  # XOR операция между байтами
        return '{:02X}'.format(checksum)  # Форматируем результат в виде двух символов в шестнадцатеричном формате


class NmeaHDT(NmeaSentence):
    def upd_data(self, data: list) -> bytes:
        course = data[0]
        MESSAGE = f"$GPHDT,{course},T"
        checksum = self.calculate_checksum(bytearray(MESSAGE.encode('ascii')))
        MESSAGE = f"{MESSAGE}*{checksum}"
        self.data = MESSAGE.encode('ascii')
        return self.data


class NmeaRMC(NmeaSentence):
    def upd_data(self, data: list) -> bytes:
        time = data[0]
        lat_ddmm = data[1]
        lon_ddmm = data[2]
        speed = data[3]
        heading = data[4]
        date = data[5]
        MESSAGE = f"$GPRMC,{time},A,{lat_ddmm},N,{lon_ddmm},E,{speed},{heading},{date},,,"
        checksum = self.calculate_checksum(bytearray(MESSAGE.encode('ascii')))
        MESSAGE = f"{MESSAGE}*{checksum}"
        self.data = MESSAGE.encode('ascii')
        return self.data


class MoveCalc:
    def __init__(self, lat_start_ddmm: float = 4454.5453, lon_start_ddmm: float = 3716.1331,
                 speed: float = 0, course: float = 0):
        self.lat_start_ddmm = lat_start_ddmm  # широта начальной точки (Москва в формате DDMM.MM)
        self.lon_start_ddmm = lon_start_ddmm  # долгота начальной точки (Москва в формате DDMM.MM)
        self.course = course  # курс в градусах (на северо-восток)
        self.speed = speed  # скорость в м/с
        self.HDT = NmeaHDT()
        self.RMC = NmeaRMC()

    def udp_data_parse(self, data: bytes):
        # data, address = sock.recvfrom(100)  # 4096 - максимальный размер буфера
        # print(f'Received {len(data)} bytes from {address}')
        self.rudder_angle = struct.unpack('b', data[0:1])[0]  # 'b' для 8-битного целого числа со знаком
        # print(f'Received angle: {angle}')
        speed = struct.unpack('b', data[1:2])[0]  # 'b' для 8-битного целого числа со знаком
        self.gear = struct.unpack('b', data[2:3])[0]  # 'b' для 8-битного целого числа со знаком
        # 0 - neutral
        # 1 - drive
        # 2 - reverse
        if self.gear != 0:
            speed = speed * 0.6  # 60 kph max
            self.speed = speed * 0.277778  # to m/s
        else:
            self.speed = 0
        print(f'Received angle: {self.rudder_angle}, Received speed: {self.speed}, Received gear: {self.gear}')
        #return angle, speed, gear

    def calculate_new_position_ddmm(self):
        # Конвертируем широту и долготу из формата DDMM.MM в градусы
        lat_deg = int(self.lat_start_ddmm // 100) + (self.lat_start_ddmm % 100) / 60
        lon_deg = int(self.lon_start_ddmm // 100) + (self.lon_start_ddmm % 100) / 60

        # Переводим начальные координаты в радианы
        lat_rad = math.radians(lat_deg)
        lon_rad = math.radians(lon_deg)

        # Переводим курс в радианы
        course_rad = math.radians(self.course)

        # Вычисляем расстояние, пройденное за данный интервал времени
        distance = self.speed * 0.1  # в метрах

        # Радиус Земли в метрах
        R = 6371000

        # Новая широта в радианах
        new_lat_rad = math.asin(math.sin(lat_rad) * math.cos(distance / R) +
                                math.cos(lat_rad) * math.sin(distance / R) * math.cos(course_rad))

        # Новая долгота в радианах
        new_lon_rad = lon_rad + math.atan2(math.sin(course_rad) * math.sin(distance / R) * math.cos(lat_rad),
                                           math.cos(distance / R) - math.sin(lat_rad) * math.sin(new_lat_rad))

        # Конвертируем новые координаты в градусы
        new_lat_deg = math.degrees(new_lat_rad)
        new_lon_deg = math.degrees(new_lon_rad)

        # Конвертируем координаты в формат DDMM.MM
        new_lat_ddmm = int(new_lat_deg) * 100 + (new_lat_deg - int(new_lat_deg)) * 60
        new_lon_ddmm = int(new_lon_deg) * 100 + (new_lon_deg - int(new_lon_deg)) * 60

        return new_lat_ddmm, new_lon_ddmm

    def new_coords_with_gear(self):
        if self.gear != 2:
            lat_new_ddmm, lon_new_ddmm = self.calculate_new_position_ddmm()
        else:
            lat_new_ddmm, lon_new_ddmm = self.calculate_new_position_ddmm()
            self.course = add_cyclic(self.course, 180, max_value=359)
        return lat_new_ddmm, lon_new_ddmm, self.course

    def calc_new_data(self, ftime: str, fdate: str) -> bytes:
        if self.gear != 2:
            self.course = add_cyclic(self.course, self.rudder_angle / 10, max_value=359)
        else:
            self.course = add_cyclic(self.course, -self.rudder_angle / 10, max_value=359)
        print(self.course)
        MESSAGE_HDT = self.HDT.upd_data([self.course])
        lat_new_ddmm, lon_new_ddmm, heading = self.new_coords_with_gear()
        self.speed = self.speed * 1.94384
        MESSAGE_RMC = self.RMC.upd_data([ftime, lat_new_ddmm, lon_new_ddmm, heading, self.speed, fdate])
        self.lat_start_ddmm = lat_new_ddmm
        self.lon_start_ddmm = lon_new_ddmm
        return MESSAGE_HDT + MESSAGE_RMC


if __name__ == "__main__":
    host = "127.0.0.1"
    port = 25565
    server = UdpServer(host, port)

    UDP_IP = "127.0.0.1"
    UDP_PORT = 25567

    print("UDP target IP: %s" % UDP_IP)
    print("UDP target port: %s" % UDP_PORT)

    #sock = socket.socket(socket.AF_INET,  # Internet
    #                     socket.SOCK_DGRAM)  # UDP

    #course = 0
    last_time = time.time()

    #lat_start_ddmm = 4454.5453  # широта начальной точки (Москва в формате DDMM.MM)
    #lon_start_ddmm = 3716.1331  # долгота начальной точки (Москва в формате DDMM.MM)
    # course = 45  # курс в градусах (на северо-восток)
    #speed = 0  # скорость в м/с

    mover = MoveCalc()

    while True:
        if server.sock is not None:
            data = server.rec_data()
            mover.udp_data_parse(data)


            utc_now = datetime.now(timezone.utc)
            formatted_date = utc_now.strftime('%d%m%y')
            formatted_time = utc_now.strftime('%H%M%S')
            current_time = time.time()

            if current_time - last_time >= 0.1:
                MESSAGE = mover.calc_new_data(formatted_time, formatted_date)

                '''
                MESSAGE_HDT = f"$GPHDT,{course},T"
                checksum_hdt = calculate_nmea_checksum(bytearray(MESSAGE_HDT.encode('ascii')))
                MESSAGE_HDT = f"{MESSAGE_HDT}*{checksum_hdt}"
                MESSAGE_HDT = MESSAGE_HDT.encode('ascii')
                '''
                # sock.sendto(MESSAGE_HDT, (UDP_IP, UDP_PORT))
                #server.send_bytes(MESSAGE_HDT, UDP_IP, UDP_PORT)

                # heading = add_cyclic(course, 180, max_value=359)
                # lat_new_ddmm, lon_new_ddmm = calculate_new_position_ddmm(lat_start_ddmm, lon_start_ddmm, course, speed)


                # MESSAGE = f"$GPRMC,{formatted_time},A,4454.5453,N,03716.1331,E,5.5,{course}.0,{formatted_date},,,"
                '''
                MESSAGE = f"$GPRMC,{formatted_time},A,{lat_new_ddmm},N,{lon_new_ddmm},E,{speed},{heading},{formatted_date},,,"
                checksum = calculate_nmea_checksum(bytearray(MESSAGE.encode('ascii')))
                MESSAGE = f"{MESSAGE}*{checksum}"
                MESSAGE = MESSAGE.encode('ascii')
                '''
                # print(MESSAGE)
                #sock.sendto(MESSAGE, (UDP_IP, UDP_PORT))
                #server.send_bytes(MESSAGE, UDP_IP, UDP_PORT)

                # sock.sendto(f'{MESSAGE}{MESSAGE_HDT}', (UDP_IP, UDP_PORT))

                server.send_bytes(MESSAGE, UDP_IP, UDP_PORT)
                last_time = current_time

    input("Нажмите Enter для выхода...")
