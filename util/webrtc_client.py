"""
WebRTC Client for Cloudflare Stream
Uses aiortc for proper WebRTC connection handling
"""

import asyncio
import numpy as np
import cv2
import threading
import queue
import time
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRecorder, MediaBlackhole
import aiohttp


class WebRTCClient:
    def __init__(self, url):
        self.url = url
        self.frame_queue = queue.Queue(maxsize=2)
        self.running = False
        self.connected = False
        self.thread = None
        self.pc = None
        self.last_frame = None
        self.error = None

    def _run_async_loop(self):
        """Run the async event loop in a separate thread"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._connect())
        except Exception as e:
            self.error = str(e)
            print(f"WebRTC Error: {e}")
        finally:
            loop.close()

    async def _connect(self):
        """Establish WebRTC connection"""
        from aiortc import RTCConfiguration, RTCIceServer

        # Configure with STUN servers for ICE gathering
        config = RTCConfiguration(
            iceServers=[
                RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
                RTCIceServer(urls=["stun:stun1.l.google.com:19302"]),
            ]
        )
        self.pc = RTCPeerConnection(configuration=config)

        # Add transceiver to receive video
        self.pc.addTransceiver("video", direction="recvonly")
        self.pc.addTransceiver("audio", direction="recvonly")

        @self.pc.on("track")
        def on_track(track):
            print(f"Received track: {track.kind}")
            if track.kind == "video":
                asyncio.ensure_future(self._receive_frames(track))

        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            print(f"Connection state: {self.pc.connectionState}")
            if self.pc.connectionState == "connected":
                self.connected = True
            elif self.pc.connectionState in ["failed", "closed", "disconnected"]:
                self.connected = False
                self.running = False

        @self.pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            print(f"ICE connection state: {self.pc.iceConnectionState}")

        # Create offer
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)

        # Wait for ICE gathering to complete
        while self.pc.iceGatheringState != "complete":
            await asyncio.sleep(0.1)

        # Get the complete SDP with ICE candidates
        local_sdp = self.pc.localDescription.sdp
        print(f"ICE gathering complete. Sending offer...")

        # Send offer to Cloudflare and get answer
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.url,
                    data=local_sdp,
                    headers={"Content-Type": "application/sdp"}
                ) as response:
                    if response.status in [200, 201]:
                        answer_sdp = await response.text()
                        answer = RTCSessionDescription(sdp=answer_sdp, type="answer")
                        await self.pc.setRemoteDescription(answer)
                        print("WebRTC connection established!")
                    else:
                        error_text = await response.text()
                        raise Exception(f"Failed to get SDP answer: {response.status} - {error_text}")
        except aiohttp.ClientError as e:
            raise Exception(f"HTTP error connecting to stream: {e}")

        # Keep the connection alive
        while self.running:
            await asyncio.sleep(0.1)

        # Cleanup
        await self.pc.close()

    async def _receive_frames(self, track):
        """Receive video frames from the track"""
        print("Starting to receive video frames...")
        while self.running:
            try:
                frame = await asyncio.wait_for(track.recv(), timeout=5.0)

                # Convert to numpy array (BGR for OpenCV)
                img = frame.to_ndarray(format="bgr24")

                # Put frame in queue (non-blocking)
                try:
                    self.frame_queue.put_nowait(img)
                    self.last_frame = img
                except queue.Full:
                    # Drop oldest frame and add new one
                    try:
                        self.frame_queue.get_nowait()
                        self.frame_queue.put_nowait(img)
                        self.last_frame = img
                    except queue.Empty:
                        pass

            except asyncio.TimeoutError:
                print("Frame receive timeout")
                continue
            except Exception as e:
                if self.running:
                    print(f"Error receiving frame: {e}")
                break

    def start(self):
        """Start the WebRTC connection in a background thread"""
        if self.running:
            return

        self.running = True
        self.error = None
        self.thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.thread.start()

        # Wait for connection with timeout
        timeout = 10
        start_time = time.time()
        while not self.connected and self.running and (time.time() - start_time) < timeout:
            if self.error:
                raise Exception(self.error)
            time.sleep(0.1)

        if not self.connected:
            self.running = False
            raise Exception("WebRTC connection timeout")

    def stop(self):
        """Stop the WebRTC connection"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        self.connected = False

    def read(self):
        """
        Read a frame (OpenCV compatible interface)
        Returns: (success, frame) tuple
        """
        if not self.running or not self.connected:
            return False, None

        try:
            frame = self.frame_queue.get(timeout=0.1)
            return True, frame
        except queue.Empty:
            # Return last frame if available
            if self.last_frame is not None:
                return True, self.last_frame.copy()
            return False, None

    def isOpened(self):
        """Check if connection is open (OpenCV compatible interface)"""
        return self.connected and self.running

    def release(self):
        """Release the connection (OpenCV compatible interface)"""
        self.stop()


def create_video_capture(url, max_retries=3, retry_delay=2):
    """
    Create a video capture object for WebRTC stream with fallback.

    Args:
        url: WebRTC stream URL
        max_retries: Number of connection attempts
        retry_delay: Delay between retries in seconds

    Returns:
        WebRTCClient object or None if connection fails
    """
    for attempt in range(max_retries):
        print(f"Connecting to WebRTC stream (attempt {attempt + 1}/{max_retries})...")

        try:
            client = WebRTCClient(url)
            client.start()

            # Verify we can read frames
            time.sleep(1)
            ret, frame = client.read()
            if ret and frame is not None:
                print("Successfully connected to WebRTC stream!")
                return client
            else:
                print("Connected but no frames received")
                client.stop()

        except Exception as e:
            print(f"Connection failed: {e}")

        if attempt < max_retries - 1:
            print(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)

    return None


if __name__ == "__main__":
    # Test the WebRTC client
    TEST_URL = "https://customer-zslwzsqjf4ht8vy9.cloudflarestream.com/ec6905680b6cdc4c6a5f3cdd2f285a54kec573507c5b74ce49b110bae2c75b8a6/webRTC/play"

    print("Testing WebRTC client...")
    client = create_video_capture(TEST_URL)

    if client:
        print("Connection successful! Displaying frames...")
        while True:
            ret, frame = client.read()
            if ret:
                cv2.imshow("WebRTC Test", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        client.release()
        cv2.destroyAllWindows()
    else:
        print("Failed to connect to WebRTC stream")
