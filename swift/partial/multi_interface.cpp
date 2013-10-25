#include <string>
#include <map>
#include <sstream>
#include <vector>
#include <string.h>
#include <sys/socket.h>
#include <netdb.h>
#include <stdlib.h>
#include <stdio.h>
#include <netinet/in.h>
#include <sys/types.h>
#include <arpa/inet.h>
#include <errno.h>
#include <net/if.h>
#include <ifaddrs.h>

#define print_error_or_success(x,addr,port,fd,fa) { if (x < 0) { \
		char msg[50]; sprintf(msg,"IPv%d %d peer %s:%d cannot send",fa,fd,addr.c_str(),port);	perror(msg); } \
		else { fprintf(stderr,"IPv%d %d peer %s:%d send successful\n",fa,fd,addr.c_str(),port);} }

#define addr_send(fd,sock,port,fa) { print_error_or_success(send(fd, sock, msg) ,get_addr_string(&sock),port,fd, \
		family_to_ip(fa)) }

#define ipv4_send(fd,port,addr) { print_error_or_success(send(fd, create_ipv4_sockaddr(port,addr), msg) \
		,addr,port,fd,4) }

#define ipv6_send(fd,port,addr,b) { print_error_or_success(send(fd, create_ipv6_sockaddr(port,addr,0,0,b), msg) \
		,addr,port,fd,6) }

using namespace std;

char *ipv4_to_if(sockaddr_in *find, std::map<string, short> pifs) {
	struct ifaddrs *addrs, *iap;
	struct sockaddr_in *sa;
	char *buf = NULL;
	short priority = 0;

	getifaddrs(&addrs);
	for (iap = addrs; iap != NULL; iap = iap->ifa_next) {
		if (iap->ifa_addr && (iap->ifa_flags & IFF_UP) && iap->ifa_addr->sa_family == AF_INET) {
			sa = (struct sockaddr_in *)(iap->ifa_addr);
			// TODO: Perhaps compare s_addr (4 bytes, with first byte depicting last number in string)
			// So depending on iap->ifa_netmask, only the last three could i.e. matter.
			if (find && find->sin_addr.s_addr == sa->sin_addr.s_addr) {
				//				fprintf(stderr, "Found interface %s with ip %s\n", iap->ifa_name, inet_ntoa(sa->sin_addr));
				return iap->ifa_name;
			}
			// Determine default interface using pifs priority
			std::map<string, short>::iterator it= pifs.find(iap->ifa_name);
			if (it != pifs.end() && it->second > priority) { // Higher number, higher priority
				find->sin_addr = sa->sin_addr;
				buf = iap->ifa_name;
				priority = it->second;
			}
		}
	}
	freeifaddrs(addrs);
	//	if (buf != NULL)
	//		fprintf(stderr, "Failed to find resembling ip. Try interface %s with ip %s %x\n", buf, inet_ntoa(find->sin_addr), find->sin_addr.s_addr);

	return buf;
}

int ipv6_to_scope_id(sockaddr_in6 *find) {
	struct ifaddrs *addrs, *iap;
	struct sockaddr_in6 *sa;
	char host[NI_MAXHOST];

	getifaddrs(&addrs);
	for (iap = addrs; iap != NULL; iap = iap->ifa_next) {
		if (iap->ifa_addr && (iap->ifa_flags & IFF_UP) && iap->ifa_addr->sa_family == AF_INET6) {
			sa = (struct sockaddr_in6 *)(iap->ifa_addr);
			if (memcmp(find->sin6_addr.s6_addr, sa->sin6_addr.s6_addr, sizeof(sa->sin6_addr.s6_addr)) == 0) {
				getnameinfo(iap->ifa_addr, sizeof(struct sockaddr_in6), host, NI_MAXHOST, NULL, 0, NI_NUMERICHOST);
				//				fprintf(stderr, "Found interface %s with scope %d\n", host, sa->sin6_scope_id);
				return sa->sin6_scope_id;
			}
		}
	}
	freeifaddrs(addrs);
	return 0;
}

int test_ifaddr() {
	struct ifaddrs *ifaddr, *ifa;
	char host[NI_MAXHOST];
	int rc;

	if (getifaddrs(&ifaddr) == -1) {
		perror("getifaddrs");
		exit(EXIT_FAILURE);
	}

	for (ifa = ifaddr; ifa != NULL; ifa = ifa->ifa_next) {
		struct sockaddr_in6 *in6 = (struct sockaddr_in6 *)ifa->ifa_addr;

		if (ifa->ifa_addr == NULL)
			continue;
		if (ifa->ifa_addr->sa_family != AF_INET6)
			continue;

		rc = getnameinfo(ifa->ifa_addr, sizeof(struct sockaddr_in6),
				host, NI_MAXHOST, NULL, 0, NI_NUMERICHOST);
		if (rc != 0) {
			printf("getnameinfo() failed: %s\n", gai_strerror(rc));
			exit(EXIT_FAILURE);
		}
		printf("dev: %-8s address: <%s> scope %d\n",
				ifa->ifa_name, host, in6->sin6_scope_id);
	}

	freeifaddrs(ifaddr);
	exit(EXIT_SUCCESS);
}

int bind_ipv4 (sockaddr_in sa) {
	int fd = socket(AF_INET, SOCK_DGRAM, 0);
	if (fd < 0) {
		perror("Creating socket failed");
	}
	std::map<string, short> pifs;
	pifs["wlan0"] = 1;
	pifs["eth0"] = 2;
	char *devname = ipv4_to_if(&sa, pifs);
	if (devname == NULL) {
		fprintf(stderr, "No interface has been found\n");
		return -1;
	}
	struct in_addr addr = sa.sin_addr;
	//	*((char *)&addr.s_addr + 3) = 1; // Change the last byte of the ip address to 1
	addr.s_addr &= ~0xff000000; // Clear the most significant byte
	addr.s_addr |= 0x01000000; // Add one to the most significant byte
	char buffer[50];
	//	fprintf(stderr, "Gateway %s, device %s\n", inet_ntoa(addr), devname);
	//	system("route del default");
	//	sprintf(buffer, "route add default gw %s dev %s", addr.c_str(), devname);
	//	system(buffer);
	//	if (setsockopt(fd, SOL_SOCKET, SO_BINDTODEVICE, devname, strlen(devname)) < 0) { // Needs root permission??
	//		perror("Setting option failed");
	//	}
	//	fprintf(stderr, "Bind to %s:%d\n", inet_ntoa(sa.sin_addr), ntohs(sa.sin_port));
	if (bind(fd, (sockaddr*)&sa, sizeof(sa)) < 0) {
		perror("Binding failed");
	}

	return fd;
}

int bind_ipv6 (sockaddr_in6 sa) {
	int fd = socket(AF_INET6, SOCK_DGRAM, 0);
	if (fd < 0) {
		perror("Creating socket failed");
	}
	char str[40];
	inet_ntop(AF_INET6, &(sa.sin6_addr), str, sizeof(str));
	//	fprintf(stderr, "Bind to %s:%d\n", str, ntohs(sa.sin6_port));
	int no = 0;
	if (setsockopt(fd, IPPROTO_IPV6, IPV6_V6ONLY, (char *)&no, sizeof(no)) < 0 ) {
		perror("V6ONLY failed");
	}
	if (bind(fd, (sockaddr*)&sa, sizeof(sa)) < 0) {
		perror("Binding failed");
	}

	return fd;
}

sockaddr_in create_ipv4_sockaddr(int port, string addr) {
	struct sockaddr_in si;
	si.sin_family = AF_INET;
	si.sin_port = htons(port);
	inet_aton(addr.c_str(), &si.sin_addr);
	if (!si.sin_addr.s_addr) {
		perror("Address is wrong..");
	}
	return si;
}

sockaddr_in6 create_ipv6_sockaddr(int port, string addr, uint32_t flowinfo, uint32_t scope_id, bool ipv4=false) {
	struct sockaddr_in6 si;
	si.sin6_family = AF_INET6;
	//	if (ipv4) {
	//		si.sin6_family = AF_INET;
	//	}
	si.sin6_port = htons(port);
	si.sin6_flowinfo = flowinfo; // Should be 0 or 'random' number to distinguish this flow
	if (ipv4) {
		addr = "::ffff:" + addr;
	}
	inet_pton(AF_INET6, addr.c_str(), &si.sin6_addr);
	if (!si.sin6_addr.s6_addr) {
		perror("Address is wrong..");
	}
	//	char s[40];
	//	inet_ntop(AF_INET6, &(si.sin6_addr), s, sizeof(s));
	//	fprintf(stderr, "Sockaddr %d %s\n", si.sin6_family, s);
	si.sin6_scope_id = scope_id;
	if (scope_id == 0 && !ipv4) {
		si.sin6_scope_id = ipv6_to_scope_id(&si); // Interface number
	}
	return si;
}

int send(int sock, sockaddr peer, char *content) {
	return sendto(sock,content,strlen(content),0,&peer,sizeof(peer));
}

int send(int sock, sockaddr_in peer, char *content) {
	return sendto(sock,content,strlen(content),0,(struct sockaddr*)&peer,sizeof(peer));
}

int send(int sock, sockaddr_in6 peer, char *content) {
	return sendto(sock,content,strlen(content),0,(struct sockaddr*)&peer,sizeof(peer));
}

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

std::vector<int> create_own_sockets() {
	std::vector<int> fd;
	struct sockaddr_in si = create_ipv4_sockaddr(5555, "193.156.108.78");
	fd.push_back(bind_ipv4(si));
//	struct sockaddr_in6 si6 = create_ipv6_sockaddr(5556, "fe80::caf7:33ff:fe8f:d39c", 0, 0);
	struct sockaddr_in6 si6 = create_ipv6_sockaddr(5556, "::0", 0, 0);
	fd.push_back(bind_ipv6(si6));

	return fd;
}

std::vector<int> create_socket_for_each_if(bool ipv4=true, bool ipv6=true) {
	std::vector<int> fd;
	struct ifaddrs *ifaddr, *ifa;
	char host[NI_MAXHOST];
	int rc;

	if (getifaddrs(&ifaddr) == -1) {
		perror("getifaddrs");
		exit(EXIT_FAILURE);
	}

	for (ifa = ifaddr; ifa != NULL; ifa = ifa->ifa_next) {
		if ((ifa->ifa_flags & IFF_LOOPBACK) != IFF_LOOPBACK) {
		if (ifa->ifa_addr->sa_family == AF_INET && ipv4) {
			struct sockaddr_in *in = (struct sockaddr_in *)ifa->ifa_addr;
			fd.push_back(bind_ipv4(*in));
		} else if (ifa->ifa_addr->sa_family == AF_INET6 && ipv6) {
			struct sockaddr_in6 *in6 = (struct sockaddr_in6 *)ifa->ifa_addr;
			fd.push_back(bind_ipv6(*in6));
		}
		} else {
			// Ignored loopback
		}
	}

	freeifaddrs(ifaddr);

	return fd;
}

int family_to_ip(int fa) {
	if (fa == AF_INET)
		return 4;
	else if (fa == AF_INET6)
		return 6;
	else
		return -1;
}

void *get_in_addr(struct sockaddr *sa)
{
    if (sa->sa_family == AF_INET)
        return &(((struct sockaddr_in*)sa)->sin_addr);
    return &(((struct sockaddr_in6*)sa)->sin6_addr);
}

string get_addr_string(struct sockaddr *sa) {
	char s[INET6_ADDRSTRLEN];
	inet_ntop(sa->sa_family, get_in_addr(sa), s, sizeof(s));
	return string (s);
}

std::vector<sockaddr> get_peers_sockaddr(string host, unsigned short port) {
	//  AI_ADDRCONFIG: Only give address, if that family has a non loopback local address.
	struct addrinfo hints;
	memset(&hints, 0, sizeof(addrinfo));
	hints.ai_socktype=SOCK_DGRAM;
	hints.ai_flags =  AI_CANONNAME;
	struct addrinfo * ai;
	char name[100];
	std::vector<sockaddr> sa;

	char cport[5];
	sprintf(cport, "%d", port);

	if (getaddrinfo(host.c_str(), cport, &hints, &ai) < 0) {
		perror("No addrinfo..");
		return sa;
	}
	// Now we have the wanted infos in ai.
	struct addrinfo * aii;
	for (aii=ai; aii; aii=aii->ai_next) {
		if (aii->ai_addr == NULL)
			continue;

		fprintf(stderr, "Hostname: %s\n", aii->ai_canonname);

		sa.push_back((struct sockaddr)*(aii->ai_addr));
	}
	freeaddrinfo(ai);
	return sa;
}

short get_family(int fd, bool debug=false) {
	struct sockaddr sa;
	socklen_t len = sizeof(sa);
	if (getsockname(fd, &sa, &len) < 0) {
		perror("getsockname");
	}
	if (debug) {
		string addr;
		unsigned short port;
		if (sa.sa_family == AF_INET) {
			struct sockaddr_in in;
			len = sizeof(in);
			getsockname(fd, (struct sockaddr *)&in, &len);
			port = ntohs(in.sin_port);
			addr = inet_ntoa(in.sin_addr);
		} else if (sa.sa_family == AF_INET6) {
			struct sockaddr_in6 in6;
			len = sizeof(in6);
			getsockname(fd, (struct sockaddr *)&in6, &len);
			port = ntohs(in6.sin6_port);
			char s[40];
			inet_ntop(AF_INET6, &(in6.sin6_addr), s, sizeof(s));
			string str(s);
			addr = str;
		}
		fprintf(stderr,"Socket %s:%d\n",addr.c_str(),port);
	}
	return sa.sa_family;
}

int main(int argc, char *argv[]) {
	std::vector<int> fd = create_own_sockets();//create_socket_for_each_if();
	if (fd.size() <= 0) {
		perror("No sockets..");
		return -1;
	}

	int port1 = 55555;
	int port2 = 428;
	string addr1 = "193.156.108.67";
	string addr2 = "130.161.211.194";
	string addr3 = "fe80::218:deff:fee2:5ba6";
	string addr4 = "www.google.com";

//	std::vector<sockaddr> sa = get_peers_sockaddr(addr1,port1);
//	std::vector<sockaddr> sa1 = get_peers_sockaddr(addr2,port2);
//	std::vector<sockaddr> sa2 = get_peers_sockaddr(addr3,port1);
//	std::vector<sockaddr> sa3 = get_peers_sockaddr(addr4,port1);
//	sa.insert(sa.end(), sa1.begin(), sa1.end() );
//	sa.insert(sa.end(), sa2.begin(), sa2.end() );
//	sa.insert(sa.end(), sa3.begin(), sa3.end() );

	for (int i = 0; i < fd.size(); i++) {
		short fa = get_family(fd[i], true);

		char msg[10];
		sprintf(msg, "testing %d", fd[i]);

//		for (int j = 0; j < sa.size(); j++) {
//			addr_send(fd[i],sa[j],port1,fa);
//		}

		if (fa == AF_INET) {
			ipv4_send(fd[i],port1,addr1);
			ipv4_send(fd[i],port2,addr2);
		} else if (fa == AF_INET6) {
			ipv6_send(fd[i],port1, addr1,true);
			ipv6_send(fd[i],port2, addr3,false);
		} else {
			fprintf(stderr,"Unknown family: %d\n", fa);
		}
	}
	return 0;
}
