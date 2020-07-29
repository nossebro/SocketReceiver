# SocketReceiver

A Streamlabs Chatbot (SLCB) Script that uses [websocket-sharp](https://github.com/sta/websocket-sharp) to receive events from the local socket.

## Installation

1. Use this repository as a Template for a new script.
2. Modify the `LocalSocketEvent` function, to handle whatever events you want to.
3. Install the script in SLCB. (Please make sure you have configured the correct [32-bit Python 2.7.13](https://www.python.org/ftp/python/2.7.13/python-2.7.13.msi) Lib-directory).
4. Insert the API_Key.js by right-click the script in SLCB.
5. Reload all scripts, so the new API_Key.js file gets picked up.
6. Review the script's configuration in SLCB.

For events, you can install any or all of the SLCB mirror scripts: [StreamlabsSocketMirror](https://github.com/nossebro/StreamlabsSocketMirror), [TwitchPubSubMirror](https://github.com/nossebro/TwitchPubSubMirror) and/or [TwitchTMIMirror](https://github.com/nossebro/TwitchTMIMirror).
