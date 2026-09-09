// Measures whether a sensor reports the destination the KERNEL used, or one a
// second thread put in the buffer for it to find.
//
// One thread calls connect() over and over from a shared sockaddr. Another
// rewrites that sockaddr's port between two values as fast as it can. A sensor
// reading the caller's memory at the syscall boundary samples the buffer at one
// instant; the kernel copies it at a slightly later one, and between those two
// the value can change.
//
// Ground truth comes from connect()'s own return, which is why the two ports
// are chosen the way they are. 11434 has a listener, so the kernel using it
// returns 0. 8000 has nothing, so the kernel using it returns ECONNREFUSED at
// once. Both are on 127.0.0.1 so no packet leaves the machine, and both are
// ports idryx keeps on loopback (isLocalModelPort in decode.go), so every
// attempt is comparable against what the sensor recorded.
//
// This is a test of our own sensor against our own listener. It sends nothing
// and reaches nothing outside the machine it runs on.
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#define PORT_LISTENING 11434
#define PORT_CLOSED 8000

static struct sockaddr_in shared;
static volatile int running = 1;
static int listen_fd;

// Flips the port under the caller. Nothing else.
//
// The volatile pointer and the two spins are both load-bearing, and the first
// version of this file had neither. Two adjacent stores to the same field make
// the first one dead, and -O2 deleted it: the buffer then held PORT_CLOSED for
// the whole run, ground truth came back 20000 to 0, and both sensors agreed
// with it because there was no race to lose. A probe that quietly stops racing
// reports two sensors as identical, which is the shape of a test that proves
// nothing.
static void *racer(void *arg) {
	(void)arg;
	volatile unsigned short *port = (volatile unsigned short *)&shared.sin_port;
	while (running) {
		*port = htons(PORT_LISTENING);
		for (volatile int i = 0; i < 40; i++) {
		}
		*port = htons(PORT_CLOSED);
		for (volatile int i = 0; i < 40; i++) {
		}
	}
	return NULL;
}

// Drains the listener so its accept queue cannot fill and turn a refused
// connection into a hanging one, which would end the measurement rather than
// bias it.
static void *accepter(void *arg) {
	(void)arg;
	while (running) {
		int c = accept(listen_fd, NULL, NULL);
		if (c >= 0)
			close(c);
	}
	return NULL;
}

int main(int argc, char **argv) {
	int n = argc > 1 ? atoi(argv[1]) : 20000;

	listen_fd = socket(AF_INET, SOCK_STREAM, 0);
	int one = 1;
	setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
	struct sockaddr_in la;
	memset(&la, 0, sizeof la);
	la.sin_family = AF_INET;
	la.sin_port = htons(PORT_LISTENING);
	inet_pton(AF_INET, "127.0.0.1", &la.sin_addr);
	if (bind(listen_fd, (struct sockaddr *)&la, sizeof la) < 0) {
		perror("bind");
		return 1;
	}
	listen(listen_fd, 1024);

	memset(&shared, 0, sizeof shared);
	shared.sin_family = AF_INET;
	inet_pton(AF_INET, "127.0.0.1", &shared.sin_addr);
	shared.sin_port = htons(PORT_CLOSED);

	pthread_t r, a;
	pthread_create(&r, NULL, racer, NULL);
	pthread_create(&a, NULL, accepter, NULL);

	int used_listening = 0, used_closed = 0, other = 0;
	for (int i = 0; i < n; i++) {
		int fd = socket(AF_INET, SOCK_STREAM, 0);
		if (fd < 0)
			break;
		int rc = connect(fd, (struct sockaddr *)&shared, sizeof shared);
		if (rc == 0)
			used_listening++;
		else if (errno == ECONNREFUSED)
			used_closed++;
		else
			other++;
		close(fd);
	}

	running = 0;
	pthread_join(r, NULL);
	shutdown(listen_fd, SHUT_RDWR);
	close(listen_fd);
	pthread_cancel(a);
	pthread_join(a, NULL);

	printf("GROUND TRUTH (connect's own return): %d used :%d, %d used :%d, %d other\n",
	       used_listening, PORT_LISTENING, used_closed, PORT_CLOSED, other);
	return 0;
}
