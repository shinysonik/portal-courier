> ++The Docker zero-trust setup++

`1.deploy-zerotrust-network.sh`

- Role: Host setup.
- What it does: Creates the isolated Docker/Podman bridge network (playwright-net / br-playwright) and  applies zero-trust iptables firewall rules (blocks all WAN egress, blocks port 53 DNS, drops host SSH 22, and allows only the MITM proxy port).
- Execution: Run once with root privileges on the Linux host (sudo ./[deploy-zerotrust-network.sh](http://deploy-zerotrust-network.sh)).

`2.run-playwright-container.sh`

- Role: Container runner.
- What it does: Spawns the disposable (--rm), hardened Playwright container attached to the isolated network, passing all HTTP/HTTPS proxy environment variables with automatic TTY detection for both interactive and CI/CD use.
- Execution: ./[run-playwright-container.sh](http://run-playwright-container.sh)

`3.verify-zerotrust.sh`

- Role: Security & confinement test suite.
- What it does: Pure-Bash verification script (zero dependencies, no nc needed) that tests all 4 security boundaries (verifies internet is blocked, DNS is blocked, host SSH is blocked, and proxy is reachable).
- Execution: Run inside the container or via ./[run-playwright-container.sh](http://run-playwright-container.sh) "" /path/to/[verify-zerotrust.sh](http://verify-zerotrust.sh).

---

---

> ++**Execution Instructions**++
>
> Setup host network & firewall rules (run as root)
>
> > > `sudo ./deploy-zerotrust-network.sh`  
>
> Launch the isolated container
>
> > > `run-playwright-container.sh`
>
> Inside the container, run the verification check
>
> > > `./verify-zerotrust.sh`

