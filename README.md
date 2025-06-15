# Controll your Mouse with a Controller
---
## Install
### uvdev rules (to run the programm without sudo)
```sh
sudo groupdadd -f uinput
sudo usermod -aG uinput {USERNAME}
```

Create a rule in the `/etc/udev/rules.d` directory.
`/etc/udev/rules.d/99-uinput.rules`
```
KERNEL==”uinput”, GROUP=”uinput”, MODE:=”0660″
```

### dependencis
python:
- evdev
- numpy

### clone git
```sh
git clone https://github.com/MuedeHydra/HydraInput
python HydraInput/src/HydraInput.py
```

---

## Edit keybindings
There is an example configuration file in the folder. You can copy it to your `.conf` file and edit it.
```sh
mkdir -p ~/.config/HydraInput
cp HydraInput/HydraInput.conf ~/.config/HydraInput
```
