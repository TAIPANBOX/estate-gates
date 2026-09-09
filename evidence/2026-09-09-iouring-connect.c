// Makes exactly one outbound TCP connection through io_uring's IORING_OP_CONNECT
// and nothing else, so a sensor either saw it or did not.
//
// The destination is 127.0.0.1:11434, Ollama's port: loopback so no packet
// leaves the machine, and 11434 because idryx keeps loopback flows only on the
// local model ports (see isLocalModelPort in decode.go). Nothing is listening,
// so the connect fails immediately with ECONNREFUSED, which is fine: the sensor
// attaches where the connection is INITIATED, not where it succeeds.
#include <arpa/inet.h>
#include <liburing.h>
#include <netinet/in.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

int main(void) {
	struct io_uring ring;
	int rc = io_uring_queue_init(8, &ring, 0);
	if (rc < 0) {
		fprintf(stderr, "io_uring_queue_init: %s\n", strerror(-rc));
		return 1;
	}

	int fd = socket(AF_INET, SOCK_STREAM, 0);
	if (fd < 0) {
		perror("socket");
		return 1;
	}

	struct sockaddr_in a;
	memset(&a, 0, sizeof a);
	a.sin_family = AF_INET;
	a.sin_port = htons(11434);
	inet_pton(AF_INET, "127.0.0.1", &a.sin_addr);

	struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
	io_uring_prep_connect(sqe, fd, (struct sockaddr *)&a, sizeof a);
	io_uring_submit(&ring);

	struct io_uring_cqe *cqe;
	rc = io_uring_wait_cqe(&ring, &cqe);
	if (rc < 0) {
		fprintf(stderr, "io_uring_wait_cqe: %s\n", strerror(-rc));
		return 1;
	}
	printf("io_uring IORING_OP_CONNECT to 127.0.0.1:11434 returned %d (%s)\n",
	       cqe->res, cqe->res < 0 ? strerror(-cqe->res) : "connected");
	io_uring_cqe_seen(&ring, cqe);

	close(fd);
	io_uring_queue_exit(&ring);
	return 0;
}
