package main

import (
	"encoding/json"
	"os"
	"runtime"

	"github.com/containerd/containerd/v2/contrib/seccomp"
	"github.com/opencontainers/runtime-spec/specs-go"
)

func main() {
	if runtime.GOOS != "linux" || runtime.GOARCH != "amd64" {
		panic("generate this profile on linux/amd64 for heavy-control")
	}
	profile := seccomp.DefaultProfile(&specs.Spec{
		Process: &specs.Process{Capabilities: &specs.LinuxCapabilities{}},
	})
	profile.Syscalls = append(profile.Syscalls, specs.LinuxSyscall{
		Names: []string{"clone", "setns", "unshare", "chroot"},
		Action: specs.ActAllow,
	})
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(profile); err != nil {
		panic(err)
	}
}
