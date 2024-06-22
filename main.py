import socket
import time
from datetime import datetime, timezone


def calculate_nmea_checksum(sentence_bytes):
    checksum = 0
    for byte in sentence_bytes[1:]:
        checksum ^= byte  # XOR операция между байтами
    return '{:02X}'.format(checksum)  # Форматируем результат в виде двух символов в шестнадцатеричном формате


UDP_IP = "127.0.0.1"
UDP_PORT = 5005
print("UDP target IP: %s" % UDP_IP)
print("UDP target port: %s" % UDP_PORT)

sock = socket.socket(socket.AF_INET, # Internet
                     socket.SOCK_DGRAM) # UDP
while True:
    utc_now = datetime.now(timezone.utc)
    formatted_date = utc_now.strftime('%d%m%y')
    formatted_time = utc_now.strftime('%H%M%S')
#    MESSAGE = f"$GPRMC,{formatted_time},A,5955.2368,N,03014.5678,E,5.5,133.4,{formatted_date},,,"
    MESSAGE = f"$GPRMC,{formatted_time},A,4454.5453,N,03716.1331,E,5.5,133.4,{formatted_date},,,"
    checksum = calculate_nmea_checksum(bytearray(MESSAGE.encode('ascii')))
    MESSAGE = f"{MESSAGE}*{checksum}"
    MESSAGE = MESSAGE.encode('ascii')
    # print(MESSAGE)
    sock.sendto(MESSAGE, (UDP_IP, UDP_PORT))
    time.sleep(1)
