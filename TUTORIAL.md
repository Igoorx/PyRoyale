# How to setup the Mario Royale server emulator.

This setup guide will only cover Windows and Linux. However, the emulator should work in every platform that python works.
Also it is worth noting that I will not teach how to do port forwarding.

## Windows

There's two options, or you download one binary from [releases page](https://github.com/Igoorx/PyRoyale/releases) or you install python and setup it.
In this guide we will use the first option.

### 1 - Get the server to run

Download the "server.zip" from [releases page](https://github.com/Igoorx/PyRoyale/releases) and extract somewhere in your PC, after that, go to the extracted folder and run the `server.exe`

![ScreenShot](https://i.imgur.com/uEGkncc.png)

If some Firewall window pops-up, just click in `Allow`.

### 2 - Get the website to run

You will need to download the website, but i can't share it here for reasons, but you can find help with it in [our discord](https://discord.gg/RqszZY6), after downloading the website, it will come compressed, just extract it somewhere and go to the extracted folder and run the `VerySimpleWebServer.exe` as admin.
- If you want you can use another webserver like apache or nginx, but you will need to know how to setup these webservers to the game work properly.

![ScreenShot](https://i.imgur.com/V7pGSkg.png)

#### 2.1 - Setup Game JS

You will need also to setup the Game JS, in VerySimpleWebServer's folder, follow this path: `www\royale\js`, then open the `game.min.js` in a Text Editor of your choice.

![ScreenShot](https://i.imgur.com/nwi4JgN.png)

After opening it, search (CTRL+F) the text `WS open event has unexpected result.`, you will end up in something like this:

![ScreenShot](https://i.imgur.com/XhObkQ7.png)

In here you will find the text `infernoplus.com` or `77.68.80.27`, replace it to `127.0.0.1:9000`

![ScreenShot](https://i.imgur.com/4fS0Qic.png)

### 3 - Profit

If you did everything right, the game should be working now, just open the url: [http://127.0.0.1:8080/royale/index.html](http://127.0.0.1:8080/royale/index.html)

![ScreenShot](https://i.imgur.com/8g4f6Sc.png)

## Linux

In linux there's only one option, setup everything from the base.

### 1 - Get python and git

Use your OS package manager to install `git`, `python2.7` and `python-pip`, in debian or ubuntu you can use apt-get like this:
`sudo apt-get install git`
`sudo apt-get install python2.7`
`sudo apt-get install python-pip`

### 2 - Download this repository, install it's dependencies and run the server

To download this repository just go to some path and run this command:
`git clone https://github.com/Igoorx/PyRoyale.git`
The server will be at `./PyRoyale` path, so just run `cd PyRoyale`

After that, run these commands to install the dependencies:
`sudo pip install twisted`
`sudo pip install autobahn`
`sudo pip install emoji`
`sudo pip install configparser`

now just run the command `python server.py </dev/null &>/dev/null &` to start the server.

### 3 - Get the website to run

To get the website running, you will need `nginx`, just download it with your OS package manager, in debian or ubuntu you can use apt-get like this:
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

Now, save the file. To the changes be applied, restart the nginx service, this command should work:
`sudo /etc/init.d/nginx restart`

### 4 - Setup the website

You will need to download the website, but I can't share it here for reasons, but you can find help with it in [our discord](https://discord.gg/RqszZY6), after downloading the website, it will come compressed, just extract it somewhere then go to the extracted directory.

In the extracted directory, open the file `www/royale/js/game.min.js` in a Text Editor of your choice (I recommend VIM again) and search for `/ws`
![ScreenShot](https://i.imgur.com/MOd5EDe.png)

In here you will find the text `infernoplus.com` or `77.68.80.27`, replace it to `127.0.0.1:9000`, and save the file.

Now just run the following command to move the website files to the nginx root.
`sudo mv www/royale /var/www/html/royale`

### 5 - Profit

If you did everything right, the game should be working now, just open the url: [http://127.0.0.1:8080/royale/index.html](http://127.0.0.1:8080/royale/index.html)
