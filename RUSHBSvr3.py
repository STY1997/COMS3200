import socket
import sys
import time

LOCALHOST = "127.0.0.1"
RECV_SIZE = 1500  # recive size
PAYLOAD_SIZE = 1464  # payload size

STATUS = {
    'RESERVED': '000000', 
    'VER': '010',
    
    'DAT': '0001000',
    'FIN': '0000100', 
    'ACK': '1000000', 
    'NAK': '0100000', 
    'GET': '0010000',
    'CHK': '0000010',   
    'ENC': '0000001',
    
    'DAT_ACK': '1001000', 
    'DAT_NAK': '0101000', 
    'ACK_FIN': '1000100',
    'GET_CHK': '0010010',
    'FIN_CHK': '0000110',
    'DAT_CHK': '0001010',
    'DAT_ACK_CHK': '1001010',
    'FIN_ACK_CHK': '1000110',
    }

# change byte to int
def bytes_to_int(data):
    return int.from_bytes(data, byteorder='big')

# change string to int
def str_to_int(string, pad=PAYLOAD_SIZE):
    b_str = string.encode('utf-8')
    if pad is not None:
        for i in range(len(string), pad):
            b_str += b'\0'
    return bytes_to_int(b_str)

# change int to bytes
def int_to_bytes(integer, size=PAYLOAD_SIZE):
    return integer.to_bytes(size, byteorder='big').rstrip(b'\x00')

# convert integer to binary(16 bits long)
def int_to_bin(integer):
    return bin(integer)[2:].zfill(16)

def compute_checksum(message):
    b_str = message
    if len(b_str) % 2 == 1:
        b_str += b'\00'
    checksum = 0
    for i in range(0, len(b_str), 2):
        w = b_str[i] + (b_str[i + 1] << 8)
        checksum = carry_around_add(checksum, w)
    return ~checksum & 0xffff

def carry_around_add(a, b):
    c = a + b
    return (c & 0xffff) + (c >> 16)


class RushB:
    
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((LOCALHOST, 0))
        self.sequence = 0
        self.file = ''
        self.client_sequence = 0
        self.packet = b''
        self.client_list = []

    def server(self):
        
        self.generate_port()
        
        while True:
            #print("0")
            # if self.packet:
            #     try:
            #         data, address = self.socket.recvfrom(RECV_SIZE)
            #     except socket.timeout:
            #         print("fk")
            #         self.resend_packet(address)
            #         continue
            # else:
            #     data, address = self.socket.recvfrom(RECV_SIZE)
            
            for i in range(len(self.client_list)):
                if self.client_list[i].is_time_expire(time.time()) == True:
                    #print(self.client_list[i].get_address())
                    self.resend_packet(self.client_list[i], self.client_list[i].get_address())
                    self.client_list[i].set_time(time.time())
                    
                    
                    
            self.socket.settimeout(0.5)
            
 
            try:
                data, address = self.socket.recvfrom(RECV_SIZE)
            except socket.timeout:

                self.socket.settimeout(None)
                continue

            
        
            sequence_num, ack_num, checksum, flags, reserved, ver = self.unpack_packet(data)
                    
            client = None
            for i in range(len(self.client_list)):
                if address[1] == self.client_list[i].get_client_name():
                    client = self.client_list[i]
                    break
              
            
            if client is None:
                if sequence_num == 1 and ack_num == 0:
                    if flags == STATUS["GET"] or flags == STATUS["GET_CHK"]:
                        client = Client()
                        client.set_name(address[1])
                        client.set_address(address)
                        #print(client.get_address())
                        client.set_time(time.time())
                        if flags == STATUS["GET_CHK"]:
                            client.set_checksum(True)
                        self.client_list.append(client)
                    else:
                        continue
                else:
                    continue
            
                   
            print(len(self.client_list))    
    
            if reserved == STATUS['RESERVED'] and ver == STATUS['VER']:
                
                if flags == STATUS['GET'] and sequence_num == 1 and ack_num == 0 and checksum == 0:
                    file_name = self.get_filename(data[8:])
                    if file_name:
                        try:
                            #self.file = self.read_file(file_name)
                            client.set_file(self.read_file(file_name))
                        except Exception:
                            self.client_list.remove(client)
                            # self.socket.close()
                            # sys.exit()
                        self.send_dat(client, address, sequence_num)
                        
                elif flags == STATUS['DAT_ACK'] and sequence_num == client.get_client_seq() + 1 and ack_num == client.get_sequence() and checksum == 0:
                    # if self.file:
                    if client.get_file():
                        self.send_dat(client, address, sequence_num)
                    else:
                        self.send_packct(client, address, sequence_num, 0, STATUS['FIN'])
                        client.set_client_seq(sequence_num)
                        
                elif flags == STATUS['DAT_NAK'] and sequence_num == client.get_client_seq() + 1 and ack_num == client.get_sequence() and checksum == 0:
                    if client.get_packet():
                        self.resend_packet(client, address)
                        client.set_client_seq(sequence_num)
                        
                elif flags == STATUS['ACK_FIN'] and sequence_num == client.get_client_seq() + 1 and ack_num == client.get_sequence() and checksum == 0:
                    self.send_packct(client, address, sequence_num, sequence_num, STATUS['ACK_FIN'])
                    self.client_list.remove(client)
                    print(len(self.client_list))
                    #self.socket.close()
                    #sys.exit()
                            
                elif flags == STATUS['GET_CHK'] and sequence_num == 1 and ack_num == 0:
                    if checksum == compute_checksum(self.get_filename(data[8:])):
                        file_name = self.get_filename(data[8:])
                        if file_name:
                            client.set_file(self.read_file(file_name))
                            checksum_ = compute_checksum(client.get_file()[:PAYLOAD_SIZE].encode('utf-8'))
                            self.send_dat(client, address, sequence_num, checksum_)
                    else:
                        print('Wrong checksum in GET!')
                        
                elif flags == STATUS['DAT_ACK_CHK'] and sequence_num == client.get_client_seq() + 1 and ack_num == client.get_sequence():
                    if checksum == compute_checksum(self.get_filename(data[8:])):
                        if client.get_file():
                            checksum_ = compute_checksum(client.get_file()[:PAYLOAD_SIZE].encode('utf-8'))
                            self.send_dat(client, address, sequence_num, checksum_)
                        else:
                            self.send_packct(client, address, sequence_num, 0, STATUS['FIN_CHK'], checksum)
                            client.set_client_seq(sequence_num)
                    
                elif flags == STATUS['FIN_ACK_CHK'] and sequence_num == client.get_client_seq() + 1 and ack_num == client.get_sequence():
                    self.send_packct(client, address, sequence_num, sequence_num, STATUS['FIN_ACK_CHK'], checksum)
                    self.client_list.remove(client)
                    # self.socket.close()
                    # sys.exit()
                    
                elif checksum != 0 and checksum == compute_checksum(self.get_filename(data[8:])):
                    # print("在这里！")
                    self.resend_packet(client, address)

    def generate_port(self):
        port = self.socket.getsockname()[1]
        print(port, flush=True)
        return port

    @staticmethod
    def get_filename(payload):
        return payload.rstrip(b'\x00')

    @staticmethod
    def read_file(file_name):
        try:
            f = open(file_name, 'r')
            file = f.read()
            f.close()
        except IOError:
            print("Error: File does not exist.")
        return file

    def send_dat(self, client, address, sequence_num, checksum=None):
        #self.socket.settimeout(4)
        client.set_sequence(client.get_sequence()+1)
        #print(client.get_sequence())
        if checksum == None:
            pac = self.package(client.get_sequence(), 0, 0, STATUS['DAT'], client.get_file()[:PAYLOAD_SIZE])
            client.set_packet(pac) 
        else:
            pac = self.package(client.get_sequence(), 0, checksum, STATUS['DAT_CHK'], client.get_file()[:PAYLOAD_SIZE])
            client.set_packet(pac)
        client.set_file(client.get_file()[PAYLOAD_SIZE:])
        try:
            self.socket.sendto(client.get_packet(), address)
        except socket.error:
            print('Error: Socket Error!')
        client.set_client_seq(sequence_num)
        self.socket.settimeout(4)
        
    def send_packct(self, client, address, seq, ack, flag, checksum=None):
        #self.socket.settimeout(None)
        client.set_sequence(client.get_sequence()+1)
        if checksum == None:
            pac = self.package(client.get_sequence(), ack, 0, flag)
            client.set_packet(pac) 
        else:
            pac = self.package(client.get_sequence(), ack, checksum, flag)
            client.set_packet(pac)
        try:
            self.socket.sendto(client.get_packet(), address)
        except socket.error:
            print('Error: Socket Error!')
        # if ack == 0:
        #     self.client_sequence = seq
        self.socket.settimeout(4)

    def resend_packet(self, client, address):
        try:
            self.socket.sendto(client.get_packet(), address)
            print("Packet resended")
            self.socket.settimeout(4)
        except socket.error:
            print('ERROR: Socket Error!')

    @staticmethod
    def package(sequence_num, ack_num, checksum, flags, file=None):
        header = ''
        header += int_to_bin(sequence_num)
        header += int_to_bin(ack_num)
        header += int_to_bin(checksum)
        header += flags
        header += STATUS['RESERVED']
        header += STATUS['VER']
        header = bytes([int(header[i:i + 8], 2) for i in range(0, 64, 8)])
        if file is None:
            payload = int_to_bytes(0, PAYLOAD_SIZE)
        else:
            payload = str_to_int(file).to_bytes(PAYLOAD_SIZE, byteorder='big')
        return header + payload
    
    @staticmethod         
    def unpack_packet(data):
        sequence = bytes_to_int(data[:2])
        ack_num = bytes_to_int(data[2:4])
        checksum = bytes_to_int(data[4:6])
        rest_header = bin(bytes_to_int(data[6:8]))[2:].zfill(16)
        flag = rest_header[0:7]
        reserved = rest_header[7:13]
        ver = rest_header[13:]
        return sequence, ack_num, checksum, flag, reserved, ver

class Client:
    def __init__(self):
        self.name = ''
        self.address = ''
        self.file = ''
        self.packet = b''
        self.sequence = 0
        self.client_sequence = 0
        self.time_ = 0.0
        self.checksum = False
    
    def get_client_name(self):
        return self.name
    
    def get_address(self):
        return self.address
    
    def get_file(self):
        return self.file
    
    def get_packet(self):
        return self.packet
    
    def get_sequence(self):
        return self.sequence
    
    def get_client_seq(self):
        return self.client_sequence
    
    def get_time(self):
        return self.time_
    
    def get_checksum(self):
        return self.checksum
    
    def set_name(self, name):
        self.name = name
    
    def set_address(self, address):
        self.address = address
        
    def set_file(self, file):
        self.file = file
        
    def set_sequence(self, seq):
        self.sequence = seq
    
    def set_packet(self, packet):
        self.packet = packet
        
    def set_client_seq(self, client_sequence):
        self.client_sequence = client_sequence
        
    def set_time(self, current_time):
        self.time_ = current_time
        
    def set_checksum(self, checksum):
        self.checksum == checksum
    
    def is_time_expire(self, new_time):
        if new_time - self.time_ >= 4.0:
            return True


def main():
    RushB().server()

if __name__ == '__main__':
    main()
