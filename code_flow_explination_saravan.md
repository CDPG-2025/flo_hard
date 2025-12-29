
# Flotilla Code Flow Explanation: From Terminal to Execution

This document provides a line-by-line, file-by-file explanation of how the Flotilla framework executes a Federated Learning session. It covers the entire lifecycle, from starting the server and client in the terminal to the completion of training rounds.

---

## 1. Phase 1: System Startup (The Handshake)

Before any training happens, the Server and Client must find each other and establish communication channels.

### A. The Server Starts (`python src/flo_server.py`)

1.  **Entry Point (`flo_server.py`)**:
    *   **Line 110 (`main`)**: The script starts.
    *   **Line 114-123**: It attempts to connect to `8.8.8.8` (Google DNS) to determine its own **Public IP**. It prints this IP so you know what `--server-ip` to use on the client.
    *   **Line 128**: Initializes `FlotillaServerManager(server_config)`.
    *   **Line 21**: Initializes a Flask App (`app`).
    *   **Line 130**: Starts the HTTP Server using `waitress.serve`. This **blocks** the main thread here, listening for REST API commands (like "Start Session") on port 12345.

2.  **Server Manager Initialization (`src/server/server_manager.py`)**:
    *   **Line 20 (`FlotillaServerManager.__init__`)**:
    *   **Line 28**: Connects to **Redis** using `StateManager`. Redis will store the list of active clients.
    *   **Line 40**: Initializes `MQTTManager`.
    *   **Line 42-48**: Starts a **background thread** (`MQTT_Task_Thread`) running `mqtt_obj.mqtt_ad`. This allows the server to listen for clients via MQTT while the main thread listens for HTTP commands.

3.  **MQTT Listening (`src/server/server_mqtt_manager.py`)**:
    *   **Line 37 (`mqtt_ad`)**:
    *   **Line 155**: Connects to the MQTT Broker (Mosquitto) on port 1884.
    *   **Line 180**: Publishes an **Advertisement** ("I am here") to the topic `advert_server`.
    *   **Line 43**: Subscribes to `advert_client` (waiting for clients to say "I am here").

---

### B. The Client Starts (`python src/flo_client.py`)

1.  **Entry Point (`flo_client.py`)**:
    *   **Line 18 (`main`)**: The script starts.
    *   **Line 23-44**: Parses arguments, specifically `--server-ip` and `--client-num`.
    *   **Line 60-95**: Modifies configuration in-memory.
        *   If `--client-num` > 1, it updates port numbers (50053 -> 50055, etc.) and temp directories so multiple clients can run on one machine.
        *   It sets the `mqtt_broker` to the provided `--server-ip`.
    *   **Line 101**: Generates a unique `client_id` (UUID).
    *   **Line 114**: Initializes `ClientManager`.
    *   **Line 116**: Calls `client.run()`.

2.  **Client Running (`src/client/client_manager.py`)**:
    *   **Line 141 (`run`)**:
    *   **Line 155 (`grpc_init`)**: Starts a **gRPC Server** on the client's machine (e.g., port 50053). This waits for commands like `StartTraining` from the server.
    *   **Line 158 (`mqtt_init`)**: Starts a background thread for MQTT.
    *   **Line 161**: enters `stop_event.wait()` (keeps the script running forever until stopped).

3.  **Client Connection Logic (`src/client/client_mqtt_manager.py`)**:
    *   **Line 89 (`mqtt_sub`)**:
    *   **Line 147**: Connects to the MQTT Broker (on the Server's IP).
    *   **Line 96**: Subscribes to `advert_server` (listening for the Server's Ad).
    *   **Line 149 & 106 (`message_ad_response`)**: When the client receives the Server's Ad:
        1.  It constructs a payload containing its **IP Address, gRPC Port, and Hardware Info** (Line 117).
        2.  It publishes this payload to `advert_client`.
    *   **Server Side (`server_mqtt_manager.py`)**: Receives this message, extracts the Client's IP/Port, and saves it to Redis. **The handshake is complete.**

---

## 2. Phase 2: Triggering the Session

You now have a Server waiting and Clients connected. Nothing happens until you trigger a session.

### The Trigger (`python src/flo_session.py`)

1.  **Parsing Config**:
    *   **Line 91**: Reads your `my_training_config.yaml`.
    *   **Line 88**: Generates a new `session_id`.
2.  **Sending Command**:
    *   **Line 114**: Sends a generic HTTP POST request to `http://<server-ip>:12345/execute_command` containing the entire training config.

---

## 3. Phase 3: Session Execution (On Server)

### A. Handling the Request (`flo_server.py`)

1.  **Line 74 (`execute_command`)**: The Flask app receives the POST request.
2.  **Line 91**: It calls `handle_request`.
3.  **Line 55**: It uses `asyncio` to run `flo_server.run()` (which calls `FlotillaServerManager.run`).

### B. Session Manager Startup (`src/server/server_manager.py`)

1.  **Line 50 (`run`)**:
2.  **Line 58**: Creates a new instance of `FloSessionManager`. This object manages *this specific training run*.
3.  **Line 69**: Calls `await session.start_session()`.

### C. The Training Loop (`src/server/server_session_manager.py`)

This is the "Brain" of the operation.

1.  **Line 275 (`start_session`)**:
    *   **Line 287**: Calls `await self.train()`.

2.  **Line 973 (`train`)**:
    *   **Line 1013 (`while` loop)**: Loops until `current_round < num_training_rounds`.
    *   **Line 1045 (`client_selection`)**: Picks which clients will participate this round (e.g., "all_clients").
    *   **Line 1090 (`send_model`)**: Sends the current Global Model to the selected clients using gRPC (`StreamFile`).
    *   **Line 1091 (`asyncio.gather`)**: This is where the magic happens. It spawns parallel tasks for every client:
        *   It calls `self.async_grpc_train(...)`.

3.  **Sending Command to Client (`async_grpc_train`)**:
    *   **Line 562**:
    *   **Line 615**: Sends a gRPC request `StartTraining` to the Client's IP/Port (found in Redis). It sends the model weights, hyperparameters (LR, batch size), and dataset ID.

---

## 4. Phase 4: Client Training (On Client)

### A. Receiving the Command (`src/client/client_grpc_manager.py`)

1.  **Line 145 (`StartTraining`)**: The Client's gRPC server receives the request.
2.  **Line 184**: Calls `self.client.Train(...)` (in `src/client/client.py`).

### B. PyTorch Training (`src/client/client.py` - inferred)

*   This file loads the data (CIFAR10/Synthetic), loads the model (CNN), and runs a standard PyTorch training loop (`forward`, `backward`, `optimizer.step`).

### C. Returning Results

1.  **Line 208 (`client_grpc_manager.py`)**: The `StartTraining` function finishes. It packs the updated **Model Weights** and **Metrics** (Accuracy/Loss) into a response.
2.  **Line 222**: Returns this response to the Server via gRPC.

---

## 5. Phase 5: Aggregation & Next Round through server

### Back on the Server (`src/server/server_session_manager.py`)

1.  **Line 659 (`grpc_train_callback`)**: As each client returns, this callback is triggered.
2.  **Line 708**: Calls `self.aggregate(...)`. This runs the **FedAvg** algorithm to combine the weights from this client with others.
3.  **Line 1016 (`train` loop)**: Waits for all clients to finish.
4.  **Line 743**: Updates the Global Model with the new aggregated weights.
5.  **Line 1013**: The loop repeats for Round 2... Round 3... until finished.

---

## Summarized Connection Flow

1.  **Terminal 1 (Server)**: `python flo_server.py` -> Opens Port 12345 (REST), 1884 (MQTT).
2.  **Terminal 2 (Client)**: `python flo_client.py` -> Connects to 1884 (MQTT), Opens Port 50053 (gRPC).
3.  **Handshake**: Client tells Server "I am at 192.168.X.X:50053".
4.  **Terminal 3 (Trigger)**: `python flo_session.py` -> POST to Server:12345.
5.  **Execution**: Server connects to Client:50053 via gRPC -> "Train this model" -> Client Trains -> "Here are weights".
6.  **Loop**: Repeats for multiple rounds.
