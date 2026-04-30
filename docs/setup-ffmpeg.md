# Install FFmpeg on Windows

`pytgcalls` natively uses FFmpeg to process and bridge raw audio/video streams securely between formats and WebRTC pipes. If you are running `sinhala-english-tutor` on Windows, you will need to install FFmpeg and make it accessible in your system's PATH.

## Step 1: Download FFmpeg for Windows

1. Navigate to the official FFmpeg Windows builds page: [gyan.dev/ffmpeg/builds/](https://www.gyan.dev/ffmpeg/builds/).
2. Scroll down to the **release builds** section.
3. Download the zipped package (e.g., `ffmpeg-release-essentials.zip` or `ffmpeg-release-full.zip`).

## Step 2: Extract FFmpeg

1. Open your `Downloads` folder.
2. Right-click the downloaded `.zip` file and select **Extract All...**
3. Select a safe, permanent location on your drive to extract the folder. 
   *(Recommended: `C:\ffmpeg`)*

Wait for the extraction to complete. When finished, inside `C:\ffmpeg`, you should see a `bin` folder (i.e. `C:\ffmpeg\bin`).

## Step 3: Add FFmpeg to your Windows PATH

Your operating system (and PyTgCalls) needs to be able to find the `ffmpeg` executable without typing the full `C:\` directory path every time.

1. Press the **Windows Key** and type `Environment Variables`.
2. Select **Edit the system environment variables**.
3. In the System Properties window, click the **Environment Variables...** button at the bottom right.
4. Under the **System variables** section (the bottom half), find the variable named **`Path`**, select it, and click **Edit**.
5. Click **New** on the right side.
6. Type the path to your extracted FFmpeg `bin` folder. For example: `C:\ffmpeg\bin`
7. Click **OK** on all three windows to save your changes.

## Step 4: Verify Installation

Open a completely **new** terminal (Command Prompt, PowerShell, or Git Bash) and type:

```bash
ffmpeg -version
```

If it successfully displays the FFmpeg version and build information, you are ready to make and receive calls with the Sinhala-English Telegram Tutor!
