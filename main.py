import socket
import time
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

def calculate_new_position_ddmm(lat_start_ddmm, lon_start_ddmm, course, speed, moving_forward=True):
    # Конвертируем широту и долготу из формата DDMM.MM в градусы
    lat_deg = int(lat_start_ddmm // 100) + (lat_start_ddmm % 100) / 60
    lon_deg = int(lon_start_ddmm // 100) + (lon_start_ddmm % 100) / 60

    # Переводим начальные координаты в радианы
    lat_rad = math.radians(lat_deg)
    lon_rad = math.radians(lon_deg)

    # Изменяем курс на противоположный, если движемся назад
    if not moving_forward:
        course = (course + 180) % 360

    # Переводим курс в радианы
    course_rad = math.radians(course)
    
    # Вычисляем расстояние, пройденное за данный интервал времени
    distance = speed * 0.1  # в метрах
    
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

def calculate_nmea_checksum(sentence_bytes):
    checksum = 0
    for byte in sentence_bytes[1:]:
        checksum ^= byte  # XOR операция между байтами
    return '{:02X}'.format(checksum)  # Форматируем результат в виде двух символов в шестнадцатеричном формате

def udp_server_init(host='192.168.1.48', port=25565):
    # Создание UDP сокета
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Привязка сокета к указанному адресу и порту
    server_address = (host, port)
    sock.bind(server_address)
    
    print(f'Server listening on {host}:{port}')
    return sock
    
    '''
    while True:
        # Получение данных
        data, address = sock.recvfrom(100)  # 4096 - максимальный размер буфера
        print(f'Received {len(data)} bytes from {address}')
        #print(data.decode())
        #print(data)
        received_value = struct.unpack('b', data[0:1])[0]  # 'b' для 8-битного целого числа со знаком
        print(f'Received integer: {received_value}')
        
        # Отправка ответа клиенту (если необходимо)
        # if data:
        #     sent = sock.sendto(b'Acknowledged', address)
        #     print(f'Sent {sent} bytes back to {address}')
    '''
def udp_rec(sock=None):
    data, address = sock.recvfrom(100)  # 4096 - максимальный размер буфера
    print(f'Received {len(data)} bytes from {address}')
    angle = struct.unpack('b', data[0:1])[0]  # 'b' для 8-битного целого числа со знаком
    #print(f'Received angle: {angle}')
    speed = struct.unpack('b', data[1:2])[0]  # 'b' для 8-битного целого числа со знаком
    gear = struct.unpack('b', data[2:3])[0]  # 'b' для 8-битного целого числа со знаком
    print(f'Received angle: {angle}, Received speed: {speed}, Received gear: {gear}')
    return angle, speed, gear

def add_cyclic(a, b, max_value=359):
    result = (a + b) % (max_value + 1)
    return result

def new_coords_with_gear(gear, lat_start_ddmm, lon_start_ddmm, course, speed):
    if gear != 2:
        lat_new_ddmm, lon_new_ddmm = calculate_new_position_ddmm(lat_start_ddmm, lon_start_ddmm, course, speed, moving_forward=True)
    else:
        lat_new_ddmm, lon_new_ddmm = calculate_new_position_ddmm(lat_start_ddmm, lon_start_ddmm, course, speed, moving_forward=False)
        course = add_cyclic(course, 180, max_value=359)
    return lat_new_ddmm, lon_new_ddmm, course

UDP_IP = "192.168.1.28"
UDP_PORT = 5005

host = "192.168.1.21"
port = 25565

print("UDP target IP: %s" % UDP_IP)
print("UDP target port: %s" % UDP_PORT)
try:
    serv_sock = udp_server_init(host, port)
except OSError as e:
    serv_sock = None
    print(f"Error: {e}")

sock = socket.socket(socket.AF_INET, # Internet
                     socket.SOCK_DGRAM) # UDP

course = 0
last_time = time.time()

lat_start_ddmm = 4454.5453  # широта начальной точки (Москва в формате DDMM.MM)
lon_start_ddmm = 3716.1331  # долгота начальной точки (Москва в формате DDMM.MM)
# course = 45  # курс в градусах (на северо-восток)
speed = 0  # скорость в м/с

while True:
    if serv_sock is not None:
        rudder_angle, speed, gear = udp_rec(serv_sock)
        # 0 - neutral
        # 1 - drive
        # 2 - reverse
        if gear != 0:
            speed = speed * 0.6 # 60 kph max
            speed = speed * 0.277778 # to m/s
        else:
            speed = 0
            
        utc_now = datetime.now(timezone.utc)
        formatted_date = utc_now.strftime('%d%m%y')
        formatted_time = utc_now.strftime('%H%M%S')
        current_time = time.time()
    
        if current_time - last_time >= 0.1:
            if gear != 2:
                course = add_cyclic(course, rudder_angle/10, max_value=359)
            else:
                course = add_cyclic(course, -rudder_angle/10, max_value=359)
            print(course)
            
            MESSAGE_HDT = f"$GPHDT,{course},T"
            checksum_hdt = calculate_nmea_checksum(bytearray(MESSAGE_HDT.encode('ascii')))
            MESSAGE_HDT = f"{MESSAGE_HDT}*{checksum_hdt}"
            MESSAGE_HDT = MESSAGE_HDT.encode('ascii')
            sock.sendto(MESSAGE_HDT, (UDP_IP, UDP_PORT))
            
                #heading = add_cyclic(course, 180, max_value=359)
            #lat_new_ddmm, lon_new_ddmm = calculate_new_position_ddmm(lat_start_ddmm, lon_start_ddmm, course, speed)
            lat_new_ddmm, lon_new_ddmm, heading = new_coords_with_gear(gear, lat_start_ddmm, lon_start_ddmm, course, speed)
            speed = speed * 1.94384
    
            #MESSAGE = f"$GPRMC,{formatted_time},A,4454.5453,N,03716.1331,E,5.5,{course}.0,{formatted_date},,,"
            MESSAGE = f"$GPRMC,{formatted_time},A,{lat_new_ddmm},N,{lon_new_ddmm},E,{speed},{heading},{formatted_date},,,"
            checksum = calculate_nmea_checksum(bytearray(MESSAGE.encode('ascii')))
            MESSAGE = f"{MESSAGE}*{checksum}"
            MESSAGE = MESSAGE.encode('ascii')
            #print(MESSAGE)
            sock.sendto(MESSAGE, (UDP_IP, UDP_PORT))
            
            #sock.sendto(f'{MESSAGE}{MESSAGE_HDT}', (UDP_IP, UDP_PORT))
    
            lat_start_ddmm = lat_new_ddmm
            lon_start_ddmm = lon_new_ddmm
    
            last_time = current_time

input("Нажмите Enter для выхода...")