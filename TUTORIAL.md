# How to setup the Mario Royale server emulator

This setup guide will only cover Windows and Linux. However, the emulator should work on every system with Python.
This guide will not teach you how to do port forwarding.

## Windows

There's two options, either you download the binary from [the releases page](https://github.com/Igoorx/PyRoyale/releases) or you install python and setit up.
In this guide, we will go with the first option.

### 1 - Get the server to run

Download the "server.zip" from [releases page](https://github.com/Igoorx/PyRoyale/releases) and extract it somewhere on your PC. After that, go to the extracted folder and run `server.exe`

![ScreenShot](https://i.imgur.com/uEGkncc.png)

If a firewall window pops up, just click `Allow`.

### 2 - Get the website to run

You will need to download the website, but i can't share it here for a few reasons. You can get help to find it on [our discord](https://discord.gg/RqszZY6). After downloading the website, it will be compressed. Just extract it somewhere and go to the extracted folder. Run the `VerySimpleWebServer.exe` as admin.
- If you want you can use another webserver like apache or nginx, but you will need to know how to setup these webservers in order to make the game work properly.

![ScreenShot](https://i.imgur.com/V7pGSkg.png)

#### 2.1 - Setup game JS

You will need also to setup the game JS. In VerySimpleWebServer's folder, follow this path: `www\royale\js`, then open the `game.min.js` in a Text Editor of your choice.

![ScreenShot](https://i.imgur.com/nwi4JgN.png)

After opening it, search (CTRL+F) for the text `WS open event has unexpected result.`. You will end up on this line:

![ScreenShot](https://i.imgur.com/XhObkQ7.png)

On this chunk of code you will find the text `infernoplus.com` or `77.68.80.27`. Replace it to `127.0.0.1:9000`

![ScreenShot](https://i.imgur.com/4fS0Qic.png)

### 3 - Profit

If you did everything right, the game should be working now. Just access the url [http://127.0.0.1:8080/royale/index.html](http://127.0.0.1:8080/royale/index.html) on your browser.

![ScreenShot](https://i.imgur.com/8g4f6Sc.png)

## Linux

On Linux there's only one option, and that's to set up everything from the base.

### 1 - Get python and git

Use your OS package manager to install `git` and `python3.7`. On Debian or Ubuntu you can use apt-get:

`sudo apt-get install git`

`sudo apt-get install python3.7`

### 2 - Download this repository, install it's dependencies and run the server

To download this repository, open the command prompt on any path and run this command:
`git clone https://github.com/Igoorx/PyRoyale.git`
The server will be on the `./PyRoyale` path, so just execute `cd PyRoyale`.

After that, run this command to install the dependencies:
`sudo python3.7 -m pip install -r requirements.txt`
- If you get the error code 1, run the command `sudo apt-get build-essential python3.7-dev`and try again.

Now just run the command `python3.7 server.py </dev/null &>/dev/null &` to start the server.

### 3 - Get the website to run

To get the website running, you will need `nginx`. Download it with your OS package manager, on Debian or Ubuntu you can, again, use apt-get:
`sudo apt-get install nginx`

After the install has completed, open the file `/etc/nginx/sites-available/default` in a Text Editor of your choice. (I recommend VIM)

Find the text `location / {` and above it write the following:

```
 location ^~ /royale {
   if (-e $request_filename.json){
       rewrite ^/(.*)$ /$1.json;
   }
 }
```

![ScreenShot](https://i.imgur.com/jGGZsYY.png)

Now, save the file. In order to apply the changes, restart the nginx service. You can use this command too:
`sudo /etc/init.d/nginx restart`

### 4 - Setup the website

You will need to download the website, but I can't share it here for a few reasons. You can get help to find it on [our discord](https://discord.gg/RqszZY6). After downloading the website, it will be compressed. Extract it somewhere then go to the extracted directory.

In the extracted directory, open the file `www/royale/js/game.min.js` in a Text Editor of your choice (Again, i recommend VIM) and search for `/ws`
![ScreenShot](https://i.imgur.com/MOd5EDe.png)

On this chunk of code, you will find the text `infernoplus.com` or `77.68.80.27`. Replace it to `127.0.0.1:9000`, and save the file.

Now just run the following command to move the website files to the nginx root.
`sudo mv www/royale /var/www/html/royale`

### 5 - Profit

If you did everything right, the game should be working now. Open the url [http://127.0.0.1/royale/index.html](http://127.0.0.1/royale/index.html) in your browser.
