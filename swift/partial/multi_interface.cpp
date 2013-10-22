#include <string>
#include <string.h>
#include <sys/socket.h>
#include <stdio.h>
#include <netinet/in.h>
#include <sys/types.h>
#include <arpa/inet.h>
#include <errno.h>

using namespace std;

int bind (sockaddr_in sa) {
	int fd = socket(AF_INET, SOCK_DGRAM, 0);
	if (fd < 0) {
		perror("Creating socket failed");
	}
	const char *devname = "wlan0";
	if (setsockopt(fd, SOL_SOCKET, SO_BINDTODEVICE, devname, strlen(devname)) < 0) { // Needs root permission??
		perror("Setting option failed");
	}
	if (bind(fd, (sockaddr*)&sa, sizeof(sa)) < 0) {
		perror("Binding failed");
	}

	return fd;
}

//int bind_raw (sockaddr_in sa) {
//	int fd = socket(AF_INET, SOCK_RAW, IPPROTO_RAW);
//	if (fd < 0) {
//		perror("Creating socket failed");
//	}
//	int on = 1;
//	if (setsockopt(fd, IPPROTO_IP, IP_HDRINCL, (char *) &on, sizeof(on)) < 0) {
//		fprintf(stderr, "Cannot set IP_HDRINCL: %s\n", strerror(errno));
//	}
//	const char *devname = "wlan0";
//	if (setsockopt(fd, SOL_SOCKET, SO_BINDTODEVICE, devname, strlen(devname)) < 0) { // Needs root permission??
//		perror("Setting option failed");
//	}
//	if (bind(fd, (sockaddr*)&sa, sizeof(sa)) < 0) {
//		perror("Binding failed");
//	}
//
//	return fd;
//}

sockaddr_in create_sockaddr(int port, char *addr) {
	struct sockaddr_in si;
	si.sin_family = AF_INET;
	si.sin_port = htons(port);
	si.sin_addr.s_addr = inet_addr(addr);
	if (!si.sin_addr.s_addr) {
		perror("Address is wrong..");
	}
	return si;
}

int send(int sock, sockaddr_in peer, char *content) {
	return sendto(sock,content,strlen(content),0,(struct sockaddr*)&peer,sizeof(peer));
}

//int send_raw(int sock, sockaddr_in peer, const char *message) {
//	struct opacket4 op4;
//	void *packet;
//	headersize = sizeof(op4.ip) + sizeof(op4.udp);
//	packetsize = headersize + strlen(message);
//	op4.ip.ip_len = htons(packetsize);
//	packet = &op4;
//	return sendto(sock,packet,strlen(message),0,(struct sockaddr*)&peer,sizeof(peer));
//}

int send_msg(int sock, sockaddr_in peer, char *content) {
	struct iovec iov[1];
	iov[0].iov_base=content;
	iov[0].iov_len=sizeof(content);

	struct msghdr message;
	message.msg_name=(struct sockaddr*)&peer;
	message.msg_namelen=sizeof(peer);
	message.msg_iov=iov;
	message.msg_iovlen=1;
	message.msg_control=0;
	message.msg_controllen=0;

	return sendmsg(sock,&message,0);
}

int main(int argc, char *argv[]) {
	printf("Main\n");
	struct sockaddr_in sock = create_sockaddr(5555, (char *) "193.156.108.78");
	int fd = bind(sock);
	if (fd < 0) {
		perror("Not really a socket..");
	}

	struct sockaddr_in peer1 = create_sockaddr(55555, (char *) "193.156.108.67");
	struct sockaddr_in peer2 = create_sockaddr(6428, (char *) "130.161.211.194");

	std::string s = "testing";
	char * msg = (char *) s.c_str();
	if (send_msg(fd, peer1, msg) < 0) {
		perror("Peer1 cannot send");
	}
	if (send_msg(fd, peer2, msg) < 0) {
		perror("Peer2 cannot send");
	}
	return 0;
}
