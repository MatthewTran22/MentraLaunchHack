# View Pew

Smart Glasses Laser Tag

https://x.com/caydengineer/status/1994585871820230984?s=20

## Run instructions

1. Run the scorekeeping API on port 8000:

```
uv sync
source .venv/bin/activate
uvicorn src.backend.main:app
```

2. Run the Mentra glasses streaming backend on port 3000:

(Follow the original README instructions below to get the app running on MentraOS first)


```
bun install
bun run dev
```

This also starts the leaderboard at http://localhost:5173/webview/leaderboard

3. Run nginx on your computer with the config at nginx.conf:

This splits your 7777 port into the backend (localhost:7777 -> 3000) and 8000 for the api (localhost:7777/api -> 8000),
and it's only due to limitations of using one ngrok plan.


```
sudo nginx -s reload -c $(pwd)/nginx.conf
```

Update anywhere where there's an ngrok URL to your URL. Verify you can hit
localhost:7777 and localhost:7777/api/docs


4. Start the computer vision/shot detection backend.
This receives the RTMP stream from the glasses and detects targets/shots

run media mtx
mediamtx mediamtx.yml
mediamtx mediamtx_player2.yml

player 1: python finger_gun_detector.py -p 1
player 2: python finger_gun_detector.py -p 2

media mtx must run before running the python scripts


4. Start the MentraOS app, run the laser tag app that corresponds to your backend, and go into the settings
to set up your username, team, and port. Restart the app to let it hit the API with the new info.

Flow: Glasses stream -> Mentra app -> your mentra backend app (registers you with scorekeeping API) -> rtmp stream on local ip -> media mtx -> computer vision python scripts -> ping scorekeeping API and play sounds for hits -> leaderboard at /webview/leaderboard pings API periodically for leaderboard data.


Some username stuff is hardcoded for the hackathon, could be improved later.


Original README:

# MentraOS-Camera-Example-App

This is a simple example app which demonstrates how to use the MentraOS Camera API to take photos and display them in a webview.

You could also send the photo to an AI api, store it in a database or cloud storage, send it to Roboflow, or do other processing.

### Install MentraOS on your phone

MentraOS install links: [mentra.glass/install](https://mentra.glass/install)

### (Easiest way to get started) Set up ngrok

1. `brew install ngrok`

2. Make an ngrok account

3. [Use ngrok to make a static address/URL](https://dashboard.ngrok.com/)

### Register your App with MentraOS

1. Navigate to [console.mentra.glass](https://console.mentra.glass/)

2. Click "Sign In", and log in with the same account you're using for MentraOS

3. Click "Create App"

4. Set a unique package name like `com.yourName.yourAppName`

5. For "Public URL", enter your Ngrok's static URL

6. In the edit app screen, add the microphone permission

### Get your App running!

1. [Install bun](https://bun.sh/docs/installation)

2. Clone this repo locally: `git clone https://github.com/Mentra-Community/MentraOS-Camera-Example-App`

3. cd into your repo, then type `bun install`

5. Set up your environment variables:
   * Create a `.env` file in the root directory by copying the example: `cp .env.example .env`
   * Edit the `.env` file with your app details:
     ```
     PORT=3000
     PACKAGE_NAME=com.yourName.yourAppName
     MENTRAOS_API_KEY=your_api_key_from_console
     ```
   * Make sure the `PACKAGE_NAME` matches what you registered in the MentraOS Console
   * Get your `API_KEY` from the MentraOS Developer Console

6. Run your app with `bun run dev`

7. To expose your app to the internet (and thus MentraOS) with ngrok, run: `ngrok http --url=<YOUR_NGROK_URL_HERE> 3000`
    * `3000` is the port. It must match what is in the app config. For example, if you entered `port: 8080`, use `8080` for ngrok instead.


### Next Steps

Check out the full documentation at [docs.mentra.glass](https://docs.mentra.glass/camera)
