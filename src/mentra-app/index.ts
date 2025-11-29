/**
 * =============================================================================
 * MentraOS Camera App - Beginner-Friendly Template
 * =============================================================================
 *
 * This app allows users to take photos using their MentraOS glasses.
 *
 * QUICK START:
 * 1. Make sure your .env file has PACKAGE_NAME and MENTRAOS_API_KEY set
 * 2. Run: bun run dev
 * 3. Visit the MentraOS Developer Console: https://console.mentra.glass/
 *
 * HOW IT WORKS:
 * - When a user presses the button on their glasses, it takes a photo
 * - When they hold the button, it toggles video streaming mode
 * - Photos are stored temporarily and can be viewed in a web interface
 *
 * =============================================================================
 */

import { AppServer, AppSession } from "@mentra/sdk";
import { setupButtonHandler } from "./event/button";
import { takePhoto } from "./modules/photo";
import { setupWebviewRoutes, broadcastTranscriptionToClients, registerSession, unregisterSession } from "./routes/routes";
// import { playAudio, speak } from "./modules/audio";
import { setupTranscription } from "./modules/transcription";
import * as path from "path";

interface StoredPhoto {
  requestId: string;
  buffer: Buffer;
  timestamp: Date;
  userId: string;
  mimeType: string;
  filename: string;
  size: number;
}

// CONFIGURATION - Load settings from .env file

const PACKAGE_NAME =
  process.env.PACKAGE_NAME ??
  (() => {
    throw new Error("PACKAGE_NAME is not set in .env file");
  })();

const MENTRAOS_API_KEY =
  process.env.MENTRAOS_API_KEY ??
  (() => {
    throw new Error("MENTRAOS_API_KEY is not set in .env file");
  })();

const PORT = parseInt(process.env.PORT || "3000");

const API_URL = process.env.API_URL // API base URL
const NGROK_URL = API_URL


// MAIN APP CLASS

class ExampleMentraOSApp extends AppServer {
  private photosMap: Map<string, StoredPhoto> = new Map();
  private webrtcUrl: string | null = null;
  private hlsUrl: string | null = null;
  private dashUrl: string | null = null;

  constructor() {
    super({
      packageName: PACKAGE_NAME,
      apiKey: MENTRAOS_API_KEY,
      port: PORT,
    });

    // Ensure JSON body parser is enabled
    const express = require("express");
    const { createProxyMiddleware } = require('http-proxy-middleware');
    this.getExpressApp().use(express.json());

    // Serve static files (audio, images, etc.) from the public directory
    const publicPath = path.join(process.cwd(), "src", "public");
    this.getExpressApp().use("/assets", express.static(publicPath + "/assets"));

    // Set up all web routes (pass our photos map)
    setupWebviewRoutes(this.getExpressApp(), this.photosMap);

    // Add endpoint to query WebRTC URL
    this.getExpressApp().get("/url", (_req: any, res: any) => {
      res.json({
        webrtcUrl: this.webrtcUrl,
        hlsUrl: this.hlsUrl,
        dashUrl: this.dashUrl,
        status: this.webrtcUrl ? "active" : "inactive"
      });
    });

    // Check if we should use Vite dev server or serve built files
    const frontendDistPath = path.join(process.cwd(), "src", "frontend", "dist");
    const useViteDevServer = process.env.NODE_ENV !== 'production' && process.env.USE_VITE_DEV === 'true';

    if (useViteDevServer) {
      // Development mode: proxy /webview to Vite dev server
      console.log('Using Vite dev server for /webview');
      this.getExpressApp().use('/webview', createProxyMiddleware({
        target: 'http://localhost:5173/webview',
        changeOrigin: true,
        ws: true, // Enable WebSocket proxying for HMR
        pathRewrite: {
          '^/webview': '' // Remove /webview prefix when proxying
        },
        onError: (err: any, _req: any, res: any) => {
          console.error('Proxy error:', err);
          res.status(500).send('Frontend dev server not running. Please start it with: npm run dev:frontend');
        }
      }));
    } else {
      // Production mode: serve the built React frontend at /webview
      console.log('Serving built frontend from', frontendDistPath);
      this.getExpressApp().use('/webview', express.static(frontendDistPath));

      // SPA fallback for /webview routes in production
      this.getExpressApp().get('/webview/*', (_req: any, res: any) => {
        res.sendFile(path.join(frontendDistPath, 'index.html'), (err: any) => {
          if (err) {
            console.error('Error serving index.html:', err);
            res.status(500).send('Frontend build not found. Please run: npm run build:frontend');
          }
        });
      });
    }
  }

  // Session Lifecycle - Called when a user opens/closes the app

  /**
   * Called when a user launches the app on their glasses
   */
  protected async onSession(
    session: AppSession,
    sessionId: string,
    userId: string
  ): Promise<void> {
    this.logger.info(`Session started for user ${userId}`);

    // Register this session for audio playback from the frontend
    registerSession(userId, session);

    // get team from settings
    const username = session.settings.get<string>("username");
    const team = session.settings.get<string>("team");
    const port = session.settings.get<number>("port");
    const ip_address = "192.168.50.149"

    const rtmp_url = `rtmp://${ip_address}:${port}/live/stream`;

    console.log(`USER IS ON TEAM: ${team}`);
    console.log(`USER NAME: ${username}`);
    console.log(`RTMP URL: ${rtmp_url}`);

    // Register player with backend API
    console.log(`Everything: ${username} ${team} ${rtmp_url}`);
    if (username && team) {
      try {
        const apiEndpoint = `${API_URL}/api/players`;
        console.log(`Registering player with API: ${apiEndpoint}`);
        
        const response = await fetch(apiEndpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(NGROK_URL ? { 'ngrok-skip-browser-warning': 'true' } : {}),
          },
          body: JSON.stringify({
            username: username,
            team: team[0], // Ensure lowercase for API
            stream_url: rtmp_url,
          }),
        });

        if (response.ok) {
          const playerData = await response.json();
          console.log('Player registered successfully:', playerData);
        } else {
          const errorText = await response.text();
          console.error(`Failed to register player: ${response.status} ${response.statusText}`, errorText);
        }
      } catch (error) {
        console.error('Error registering player with API:', error);
        // Don't throw - continue with session even if API call fails
      }
    } else {
      console.warn('Cannot register player: username or team is missing');
    }

    const cleanup = session.camera.onStreamStatus((status) => {
      console.log("RTMP status:", status.status);
      if (status.status === "active") {
        console.log("Streaming to:", session.camera.getCurrentStreamUrl());
      }
      if (status.status === "error") {
        console.error(status.errorDetails);
      }
    });

    await session.camera.startStream({
      rtmpUrl: rtmp_url,
    });

    // Note: urls are returned immediately, but viewers should connect only after
    // a status event reports status === "active".

    // // Stop when done
    // await session.camera.stopStream();

    // // Cleanup status listener
    // cleanup();
  }

  /**
   * Called when a user closes the app or disconnects
   */
  protected async onStop(
    sessionId: string,
    userId: string,
    reason: string
  ): Promise<void> {
    this.logger.info(`Session stopped for user ${userId}, reason: ${reason}`);

    // Unregister the session
    unregisterSession(userId);
  }
}

// START THE SERVER

const app = new ExampleMentraOSApp();

app.start().catch(console.error);
