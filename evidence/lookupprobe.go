// lookupprobe: does Go's resolver connect() to anything other than the
// nameserver when it resolves a name with many A records? Run under the
// sensor with --pid=host so the sensor's own traffic is excluded and every
// flow attributed to comm "lookupprobe" is this program's.
package main

import (
	"fmt"
	"net"
	"os"
)

func main() {
	for _, h := range os.Args[1:] {
		addrs, err := net.LookupHost(h)
		fmt.Printf("%-40s %d addrs err=%v\n", h, len(addrs), err)
	}
}
