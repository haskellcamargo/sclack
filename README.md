# Sclack

> The best CLI client for Slack, because everything is terrible!

![Sclack](./resources/example.png)

## Disclaimer

The project is still under alpha, there are lots of things already done, but there is also a lot of work to do! If you want to help, please contact me under marcelocamargo@linuxmail.org or create an issue! Working in community, we can soon have a CLI client as complete as the web one!

## Setup

The first thing you need to do is to get a [Slack token here](https://api.slack.com/custom-integrations/legacy-tokens).
Use, create or request a token for each workspace that you'll use on Sclack.
Not all workspaces allow you to generate a token, so sometimes you'll need to
ask for the administrator to enable the feature.

## Optional Dependencies

### Nerd Fonts

Sclack seems better when used with a [Nerd Font](https://nerdfonts.com/). Using
them is completely optional, but it is how some Sclack icons are possible.
Personally, I use [Fire Code Nerd Font](https://github.com/ryanoasis/nerd-fonts/releases/download/v2.0.0/FiraCode.zip).
Download, install and set as the default font of your terminal emulator.

### libcaca

Sclack uses `caca-utils` to create ANSI/VT100 + ASCII versions of pictures and
render them. Images will only be rendered if both `caca-utils` is installed
and `features.pictures` is configured to `true`. To install `caca-utils`, just
run `sudo apt-get install caca-utils` on Debian and `brew install caca-utils` on
OS X.

## Installation

### From Source

Ensure you have Python 3.4 or superior version.

pip
```bash
git clone https://github.com/haskellcamargo/sclack.git
cd sclack
pip install -r requirements.txt
chmod +x ./app.py
./app.py
```
pipenv
```bash
git clone https://github.com/haskellcamargo/sclack.git
cd sclack
pipenv install # install deps
pipenv shell # enter virtualenv
python app.py # run app
```

### From Binary

If you don't have Python installed, you can get the compiled binary for Sclack
on [releases](https://github.com/haskellcamargo/sclack/releases) page. Versions **will be** available for Linux x86/x64 and OS X.

## Running
Run `./app.py` after giving the correct permissions. If you don't have a `~/.sclack` file, you can generate one here by providing your workspace token. You can change the theme, enable or disable images, emojis, markdown, configure keyboards and everything else on `config.json`. Important: use `q` to quit!

### Default keybindings
```json
{
    "delete_message": "d",
    "edit_message": "e",
    "go_to_chatbox": "c",
    "go_to_profile": "p",
    "go_to_sidebar": "esc",
    "quit_application": "q",
    "set_edit_topic_mode": "t",
    "set_insert_mode": "i",
    "yank_message": "y"
}
```

The mouse support also has been programmed. You can scroll the chatbox and the sidebar and double click the channels to select.

## Tested Terminals

Sclack has been tested with the following terminal emulators:

- iTerm2
- QTerminal
- Terminal (OS X)
- Terminator
- XTerm

## Contributing

Contributions are very welcome, and there is a lot of work to do! You can...
- Check out our [open issues](https://github.com/haskellcamargo/sclack/issues)
- Provide bug reports
- Create packages for pip, apt, dnf, rpm, pacman and brew
- Improve documentation
- Implement handler for new events
- Refactor the workarounds in the code
- Create new themes
- Make things easier to configure

## Screenshots

![](./resources/example_1.png)
![](./resources/example_2.png)
![](./resources/example_3.png)
![](./resources/example_4.png)
![](./resources/example_5.png)
![](./resources/example_6.png)

<p align="center">Made with :rage: by <a href="https://github.com/haskellcamargo">@haskellcamargo</a></p>
