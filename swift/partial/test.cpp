#include <netinet/in.h>
#include <arpa/inet.h>
#include <stdlib.h>
#include <stdio.h>

int main(int argc, char *argv[]) {
	char buffer[50];
	struct sockaddr_in si;
	si.sin_family = AF_INET;
	si.sin_port = htons(12);
	inet_aton("0.0.0.0", &si.sin_addr);
	if (si.sin_addr.s_addr == 0) {
		fprintf(stderr,"Works..:)\n");
	}
	char *ip = inet_ntoa(si.sin_addr);
	short port = 1;
	sprintf(buffer, "Command with IP %s and port %d",ip, port);
	fprintf(stderr, "%s\n", buffer);
	system(buffer);
}
