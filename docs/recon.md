# M8550 Recon Notes

## 1. Docker reachability to 192.168.1.1

- Command: `docker run --rm alpine ping -c 3 192.168.1.1`
- Outcome: 3 packets transmitted, 3 received, 0% packet loss (RTT min/avg/max = 9.7/52.9/112.7 ms)
- **Decision:** collector runs in container.
