
# 2-Machines Setup Guide for Flotilla

This document outlines the necessary changes and proper configuration to run the Flotilla Client and Server on two distinct machines.

## Why Changes Are Needed

By default, Flotilla is configured for a **local simulation** where both Client and Server run on the same machine (localhost). When moving to a distributed setup (2 machines), you must ensure that:
1.  **Reachability**: The components can find each other over the network.
2.  **Binding**: Services listen on accessible network interfaces (`0.0.0.0` or specific LAN IP), not just the loopback interface (`127.0.0.1`).
3.  **Firewalls**: Network ports are open between the two machines.

## Files to Traverse and Check

You should check and potentially modify the following files depending on your deployment strategy.

### 1. `src/config/server_config.yaml`

**Purpose**: Configures the Server's listening ports and its connection to backend services (Redis, MQTT).

*   **Traverse to**: `comm_config.restful`
    *   **Check**: `rest_hostname` should be set to `"0.0.0.0"`.
    *   **Why**: This ensures the Flask/Waitress server listens on *all* network interfaces, allowing the Session Manager (if running elsewhere) to send commands.
    *   **Status**: It is currently `0.0.0.0` in the code, so **no change needed**.
*   **Traverse to**: `comm_config.mqtt` and `state.state_hostname`
    *   **Check**: These point to `localhost`.
    *   **Why**: If your Redis and MQTT Broker are running on the *same machine* as the Flotilla Server, `localhost` is correct. If you move them to a third machine, you must update these to that machine's IP.

### 2. `src/config/client_config.yaml`

**Purpose**: Configures where the Client looks for the Server (Broker).

*   **Traverse to**: `comm_config.mqtt.mqtt_broker`
    *   **Change**: Change `localhost` to the **IP Address of the Server Machine**.
    *   **Why**: The client needs to connect to the MQTT broker running on the Server. `localhost` would make it look for a broker on the client machine itself.
    *   **Alternative**: You can leave this file alone and strictly use the `--server-ip` command-line argument when starting the client (Recommended).

### 3. `src/flo_client.py`

**Purpose**: The entry point for the Client.

*   **How it handles 2 machines**: It accepts a `--server-ip` argument.
*   **Mechanism**: The code uses this IP to:
    1.  Connect to the MQTT broker.
    2.  Determine the Client's own LAN IP (via `src/client/utils/ip.py`) by checking which interface can reach the Server.
    3.  Send this LAN IP to the Server so the Server can connect back via gRPC.
*   **Action**: No code change required. Use the argument `python src/flo_client.py --server-ip <SERVER_IP>`.

### 4. `src/flo_session.py`

**Purpose**: The job submission script.

*   **How it handles 2 machines**: It accepts `--server-ip` and `--server-port`.
*   **Action**: No code change required. If you run this script from the Client machine (or a third machine), you must point it to the Server: `python src/flo_session.py --server-ip <SERVER_IP> ...`.

---

## Step-by-Step Configuration

### Machine A: The Server
*Assume IP: 192.168.1.10*

1.  **Prerequisites**: Ensure Redis and MQTT Broker (Mosquitto) are running.
2.  **Firewall**: Open ports `1884` (MQTT), `12345` (REST), and `6379` (Redis, if remote).
3.  **Run Server**:
    ```bash
    python src/flo_server.py
    ```
    *The server prints its detected IP. Verify it matches your expectation.*

### Machine B: The Client
*Assume IP: 192.168.1.20*

1.  **Firewall**: Open incoming ports `50053`, `50054` (gRPC). The Server needs to connect *inbound* to these ports on the Client.
2.  **Run Client**:
    ```bash
    python src/flo_client.py --server-ip 192.168.1.10
    ```
    *Do NOT rely on the default `localhost` in `client_config.yaml`.*

### Running a Session (From Anywhere)

If running the session trigger from Machine B:
```bash
python src/flo_session.py config/my_training_config.yaml --server-ip 192.168.1.10
```

## Summary of Changes

| File | Parameter | Change | Reason |
| :--- | :--- | :--- | :--- |
| `src/config/client_config.yaml` | `mqtt_broker` | Set to `<SERVER_IP>` | Client must find the broker. (Or use `--server-ip` arg) |
| `src/config/server_config.yaml` | `rest_hostname` | Ensure `"0.0.0.0"` | Server must accept external REST commands. |
| Network | Ports | Allow 1884, 12345, 50053+ | Firewalls often block these by default. |

**No Python code changes** are strictly necessary if you utilize the provided command-line arguments correctly.
