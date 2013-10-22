#include <sys/socket.h>
#include <stdio.h>
#include <string.h>
#include <netinet/in.h>
#include <sys/types.h>
#include <arpa/inet.h>
#include <errno.h>

int bind (sockaddr_in sa) {
	int fd = socket(AF_INET, SOCK_DGRAM, 0);
	if (fd < 0) {
		perror("Creating socket failed");
	}
//	const char *devname = "wlan0";
//	if (setsockopt(fd, SOL_SOCKET, SO_BINDTODEVICE, devname, strlen(devname)) < 0) {
//		perror("Setting option failed");
//	}
	if (bind(fd, (sockaddr*)&sa, sizeof(sa)) < 0) {
		perror("Binding failed");
	}

	return fd;
}

sockaddr_in create_sockaddr(int port, const char *addr) {
	struct sockaddr_in si;
	si.sin_family = AF_INET;
	si.sin_port = htons(port);
	si.sin_addr.s_addr = inet_addr(addr);
	if (!si.sin_addr.s_addr) {
		perror("Address is wrong..");
	}
	return si;
}

int send(int sock, sockaddr_in peer, const char *message) {
	return sendto(sock,message,sizeof(message),0,(struct sockaddr*)&peer,sizeof(peer));
}

int main(int argc, char *argv[]) {
	printf("Main\n");
	struct sockaddr_in sock = create_sockaddr(5555, "193.156.108.78");
	int fd = bind(sock);
	if (fd < 0) {
		perror("Not really a socket..");
	}

	struct sockaddr_in peer1 = create_sockaddr(55555, "193.156.108.67");
	struct sockaddr_in peer2 = create_sockaddr(6428, "130.161.211.194");

	if (send(fd, peer1, "testing") < 0) {
		perror("Peer1 cannot send");
	}
	if (send(fd, peer2, "yeah") < 0) {
		perror("Peer2 cannot send");
	}
	return 0;
}
