#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   SPDX-FileCopyrightText: 2022 Victor Fuentes <vmfuentes64@gmail.com>
#   SPDX-FileCopyrightText: 2019 Adriaan de Groot <groot@kde.org>
#   SPDX-License-Identifier: GPL-3.0-or-later
#
#   Calamares is Free Software: see the License-Identifier above.
#

import libcalamares
import os
import subprocess
import re

import gettext

_ = gettext.translation(
    "calamares-python",
    localedir=libcalamares.utils.gettext_path(),
    languages=libcalamares.utils.gettext_languages(),
    fallback=True,
).gettext


# The following strings contain pieces of a nix-configuration file.
# They are adapted from the default config generated from the nixos-generate-config command.

cfghead = """# Edit this configuration file to define what should be installed on
# your system.  Help is available in the configuration.nix(5) man page
# and in the NixOS manual (accessible by running ‘nixos-help’).

let
  home-manager = builtins.fetchTarball "https://github.com/nix-community/home-manager/archive/master.tar.gz";
  plasma-manager = builtins.fetchTarball "https://github.com/nix-community/plasma-manager/archive/trunk.tar.gz";
  desktopBackground = builtins.fetchurl "https://raw.githubusercontent.com/ParrotSec/parrot-wallpapers/refs/heads/master/backgrounds/hackthebox.jpg";
  launcherIcon = builtins.fetchurl "https://raw.githubusercontent.com/ParrotSec/parrot-themes/refs/heads/master/icons/hackthebox/start-here.svg";

  # Change these five lines to make this NixOS configuration file your own
  systemUser = "@@username@@";
  systemHostname = "@@hostname@@";
  systemTime = "@@timezone@@";
  systemLang = "@@LANG@@";
  gitName = "@@fullname@@";
in
{
  config,
  stdenv,
  fetchurl,
  lib,
  pkgs,
  ...
}:
{
  nixpkgs = {
    overlays = [

      (final: prev: {

        # Always spoof user agent to fix the problem of curl having a hard time
        # downloading certain files
        final.fetchurl = prev.fetchurl.overrideAttrs(_: {
          curlOptsList = [
            "-HUser-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            "-L"
            "-sSf"
          ];

          mirrors.gnu = [
            # This one used to redirect to a (supposedly) nearby
            # and (supposedly) up-to-date mirror but no longer does
#             "https://ftpmirror.gnu.org/"

            "https://ftp.nluug.nl/pub/gnu/"
            "https://mirrors.kernel.org/gnu/"
            "https://mirror.ibcp.fr/pub/gnu/"
            "https://mirror.dogado.de/gnu/"
            "https://mirror.tochlab.net/pub/gnu/"

            # This one is the master repository, and thus it's always up-to-date
            "https://ftp.gnu.org/pub/gnu/"

            "ftp://ftp.funet.fi/pub/mirrors/ftp.gnu.org/gnu/"
          ];
        });
      })
    ];

    # Enable CUDA support across all packages
    config = {
      cudaSupport = true;
      allowUnfree = true;
    };
  };

  imports = [
    # Include the results of the hardware scan.
    ./hardware-configuration.nix

    # Needed for ensuring desktop layout reproducibility
    (import "${home-manager}/nixos")
  ];

  # Nix package manager settings
  nix.settings = {
    # Enable flakes permanently
    experimental-features = [ "nix-command" "flakes" ];

    # Some things just don't download if you don't push things
    download-attempts = 1000000;

    # Don't abort the entire system build because some obscure download failed
    keep-going = true;

    # Fetching from master Git branches is impossible otherwise
    require-sigs = false;
  };

  # Polkit (needed for editing files as root)
  security.polkit = {
    enable = true;
    extraConfig = ''
      polkit.addRule(function(action, subject) {
        if (action.id == "org.kde.ktexteditor6.katetextbuffer")
        {
          return polkit.Result.YES;
        }
      });
    '';
  };

  # Nvidia drivers
  hardware = {
    nvidia = {
      modesetting.enable = true;
      powerManagement.enable = false;
      powerManagement.finegrained = false;
      open = true;
      nvidiaSettings = true;
      package = config.boot.kernelPackages.nvidiaPackages.beta;
    };
    graphics = {
      enable = true;
      extraPackages = with pkgs; [
        cudaPackages.cudatoolkit
        vaapiVdpau
        nvidia-vaapi-driver
      ];
    };
  };

  # Get as close to Arch as possible with rolling updates
  nix.nixPath = lib.mkOverride 0 [
    "nixpkgs=https://github.com/NixOS/nixpkgs/archive/master.tar.gz"
    "nixos=https://github.com/NixOS/nixpkgs/archive/master.tar.gz"
    "nixos-config=/etc/nixos/configuration.nix"
  ];
  
"""
cfgbootefi = """  # Bootloader.
  boot.loader.systemd-boot.enable = true;
  boot.loader.timeout = 0;
  boot.loader.efi.canTouchEfiVariables = true;
  boot.loader.efi.efiSysMountPoint = "/boot";
  
"""

cfgbootbios = """  # Bootloader.
  boot.loader.grub.enable = true;
  boot.loader.grub.device = "@@bootdev@@";
  boot.loader.grub.useOSProber = true;

"""

cfgbootbase = """  # Clean /tmp on reboot
  boot.tmp = {
    cleanOnBoot = true;
    useTmpfs = true;
    tmpfsSize = "300%";
  };

  # Plymouth
  boot.consoleLogLevel = 0;
  boot.initrd = {
    verbose = false;
    availableKernelModules = [
      "nvidia"
      "nvme"
      "xhci_pci"
      "ahci"
      "usb_storage"
      "usbhid"
      "sd_mod"
      "kvm-intel"
    ];
  };
  boot.blacklistedKernelModules = [ "nouveau" ];
  boot.plymouth.enable = true;
  boot.kernelParams = [
    "quiet"
    "splash"
    "boot.shell_on_fail"
    "nvidia_drm.modeset=1"
    "nvidia_drm.fbdev=1"
    "loglevel=3"
    "rd.systemd.show_status=false"
    "rd.udev.log_level=3"
    "udev.log_priority=3"
    "sysrq_always_enabled=1"
    "usbcore.autosuspend=\"-1\";
  ];

  boot.extraModulePackages = [ config.boot.kernelPackages.nvidiaPackages.beta ];

  # What to do in case of OOM condition
  systemd.oomd = {
    enableRootSlice = true;
    extraConfig = {
      DefaultMemoryPressureDurationSec = "2s";
    };
  };

  boot.supportedFilesystems = [
    config.fileSystems."/".fsType
    config.fileSystems."/boot".fsType
  ];

"""

cfgbootefi += cfgbootbase
cfgbootbios += cfgbootbase

cfgbootnone = """  # Disable bootloader.
  boot.loader.grub.enable = false;

"""

cfgbootgrubcrypt = """  # Setup keyfile
  boot.initrd.secrets = {
    "/boot/crypto_keyfile.bin" = null;
  };

  boot.loader.grub.enableCryptodisk = true;

"""

cfgnetwork = """  networking.hostName = "${systemHostname}"; # Define your hostname.
  # networking.wireless.enable = true;  # Enables wireless support via wpa_supplicant.

  # Configure network proxy if necessary
  # networking.proxy.default = "http://user:password@proxy:port/";
  # networking.proxy.noProxy = "127.0.0.1,localhost,internal.domain";

"""

cfgnetworkmanager = """  # Enable networking
  networking.networkmanager.enable = true;

"""

cfgtime = """  # Set your time zone.
  time.timeZone = "${systemTime}";

"""

cfglocale = """  # Select internationalisation properties.
  i18n.defaultLocale = "${systemLang}";

"""

cfglocaleextra = """  i18n.extraLocaleSettings = {
    LC_ADDRESS = "${systemLang}";
    LC_IDENTIFICATION = "${systemLang}";
    LC_MEASUREMENT = "${systemLang}";
    LC_MONETARY = "${systemLang}";
    LC_NAME = "${systemLang}";
    LC_NUMERIC = "${systemLang}";
    LC_PAPER = "${systemLang}";
    LC_TELEPHONE = "${systemLang}";
    LC_TIME = "${systemLang}";
  };

"""

cfgplasma6 = """  # Enable the X11 windowing system.
  # You can disable this if you're only using the Wayland session.
  services.xserver = {
    enable = true;
    videoDrivers = [ "nvidia" ];
  };

  # SDDM
  services.displayManager.sddm = {
    enable = true;
    wayland.enable = true;
    settings = {
      Autologin = {
        User = systemUser;
        Session = "plasma.desktop";
      };
    };
    autoLogin.relogin = true;
  };

  # KDE Plasma
  services.desktopManager.plasma6.enable = true;

"""

cfgkeymap = """  # Configure keymap in X11
  services.xserver.xkb = {
    layout = "@@kblayout@@";
    variant = "@@kbvariant@@";
  };

"""
cfgconsole = """  # Configure console keymap
  console.keyMap = "@@vconsole@@";

"""

cfgmisc = """  # Enable CUPS to print documents.
  services.printing.enable = true;

  # SSH
  services.openssh = {
    enable = true;
    settings = {
      X11Forwarding = true;
      PasswordAuthentication = true;

      # Need to quantum-proof this for OPSEC reasons
      KexAlgorithms = [ "mlkem768x25519-sha256" ];
    };
  };

  # Enable sound with pipewire.
#   sound.enable = true;
  hardware.pulseaudio.enable = lib.mkForce false;
  security.rtkit.enable = true;
  services.pipewire = {
    enable = true;
    alsa.enable = true;
    alsa.support32Bit = true;
    pulse.enable = true;
    # If you want to use JACK applications, uncomment this
    jack.enable = true;
  };

  # Enable touchpad support (enabled default in most desktopManager).
  services.libinput.enable = true;

  # Use Docker to make it easy to combine multiple pentesting distros
  # This way, if something isn't available in nixpkgs but is absolutely needed,
  # no problem, just spin up a Parrot (or Kali) Docker container
  virtualisation = {
    docker = {
      enable = true;
      storageDriver = if config.fileSystems."/".fsType == "btrfs" then "btrfs" else null;
    };

    # Since Parrot has a Docker container for BeEF Framework, including it by default
    oci-containers = {
      backend = "docker";
      containers."beef" = {
        image = "parrotsec/beef";
        autoStart = false;
        volumes = [
          "/opt/beef:/var/lib/beef-xss"
        ];
        ports = [
          "4000:3000"
        ];
        extraOptions = [
          "-ti"
          "--pull=always"
        ];
      };
    };
  };

  # Annoying ads begone!
  services.adguardhome = {
    enable = true;
    allowDHCP = true;
    openFirewall = true;
  };

"""
cfgusers = """  # Define a user account. Don't forget to set a password with ‘passwd’.
  users = {
    users."${systemUser}" = {
      isNormalUser = true;
      description = "${gitName}";
      extraGroups = [ "networkmanager" "wheel" "docker" ];
      createHome = true;
    };
  };

"""

cfgautologin = """  # Enable automatic login for the user.
  services.displayManager.autoLogin.enable = true;
  services.displayManager.autoLogin.user = "${systemUser}";

  # Sudo without password
  security.sudo.extraRules = [
    {
      users = [ "${systemUser}" ];
      commands = [
        {
          command = "ALL";
      	  options = [ "NOPASSWD" "SETENV" ];
        }
      ];
    }
  ];

"""

cfgpkgs = """  # List packages installed in system profile. To search, run:
  # $ nix search wget
  environment.systemPackages = with pkgs; [
    # Essentials
    git
    gcc
    qemu
    file
    wget
    google-chrome

    # Force this package to not use the defunct ftpmirror.gnu.org download link
    (libunistring.overrideAttrs(_: rec {
      src = pkgs.fetchurl {
        url = "https://ftp.gnu.org/gnu/libunistring/libunistring-1.2.tar.gz";
        sha256 = "sha256-/W1WYvpwZIfEg0mnWLV7wUnOlOxsMGJOyf3Ec86rvI4=";
      };
    }))

    # https://github.com/kennystrawnmusic/cryptos
    rustup
    rust-analyzer
    (vscode-with-extensions.override {
      vscodeExtensions = with vscode-extensions; [
        rust-lang.rust-analyzer
        gruntfuggly.todo-tree
        github.copilot
        github.codespaces
        tamasfe.even-better-toml
        serayuzgur.crates
        bbenoist.nix
      ]
      ++ pkgs.vscode-utils.extensionsFromVscodeMarketplace [
        {
          name = "remote-containers";
          publisher = "ms-vscode-remote";
          version = "0.327.0";
          sha256 = "sha256-nx4g73fYTm5L/1s/IHMkiYBlt3v1PobAv6/0VUrlWis=";
        }
        {
          name = "copilot-chat";
          publisher = "GitHub";
          version = "0.12.2024013003";
          sha256 = "sha256-4ArWVFko2T6ze/i+HTdXAioWC7euWCycDsQxFTrEtUw=";
        }
      ];
    })

    # For finding reverse dependencies
    nix-tree

    # System Administration
    pv

    # KDE
    kdePackages.accounts-qt
    kdePackages.akonadi
    kdePackages.akonadi-calendar
    kdePackages.akonadi-calendar-tools
    kdePackages.akonadi-contacts
    kdePackages.akonadi-import-wizard
    kdePackages.akonadi-mime
#    kdePackages.akonadi-notes
    kdePackages.akonadi-search
    kdePackages.akonadiconsole
    kdePackages.akregator
    kdePackages.alligator
    kdePackages.alpaka
    kdePackages.analitza
    kdePackages.angelfish
    kdePackages.applet-window-buttons6
    kdePackages.appstream-qt
    kdePackages.arianna
    kdePackages.ark
    kdePackages.attica
    kdePackages.audex
    kdePackages.audiocd-kio
    kdePackages.audiotube
    kdePackages.baloo
    kdePackages.baloo-widgets
    kdePackages.blinken
    kdePackages.bluedevil
    kdePackages.bluez-qt
    kdePackages.bomber
    kdePackages.bovo
    kdePackages.breeze
    kdePackages.breeze-grub
    kdePackages.breeze-gtk
    kdePackages.breeze-icons
    kdePackages.breeze-plymouth
    kdePackages.calendarsupport
    kdePackages.calindori
    kdePackages.calligra
    kdePackages.cmark
    kdePackages.colord-kde
    kdePackages.discover
    kdePackages.dolphin
    kdePackages.dolphin-plugins
    kdePackages.dragon
    kdePackages.drkonqi
    kdePackages.drumstick
    kdePackages.elisa
    kdePackages.eventviews
    kdePackages.extra-cmake-modules
    kdePackages.fcitx5-chinese-addons
    kdePackages.fcitx5-configtool
    kdePackages.fcitx5-qt
    kdePackages.fcitx5-skk-qt
    kdePackages.fcitx5-unikey
    kdePackages.fcitx5-with-addons
    kdePackages.ffmpegthumbs
    kdePackages.filelight
    kdePackages.flatpak-kcm
    kdePackages.frameworkintegration
    kdePackages.francis
    kdePackages.futuresql
    kdePackages.ghostwriter
    kdePackages.gpgme
    kdePackages.granatier
    kdePackages.grantlee-editor
    kdePackages.grantleetheme
    kdePackages.gwenview
    kdePackages.incidenceeditor
    kdePackages.juk
    kdePackages.k3b
    kdePackages.kaccounts-integration
    kdePackages.kaccounts-providers
    kdePackages.kactivitymanagerd
    kdePackages.kaddressbook
    kdePackages.kalarm
    kdePackages.kalgebra
    kdePackages.kalk
    kdePackages.kalm
    kdePackages.kalzium
    kdePackages.kamera
    kdePackages.kanagram
    kdePackages.kapidox
    kdePackages.kapman
    kdePackages.kapptemplate
    kdePackages.karchive
    kdePackages.karousel
    kdePackages.kasts
    kdePackages.kate
    kdePackages.katomic
    kdePackages.kauth
    kdePackages.kbackup
    kdePackages.kblackbox
    kdePackages.kblocks
    kdePackages.kbookmarks
    kdePackages.kbounce
    kdePackages.kbreakout
    kdePackages.kbruch
    kdePackages.kcachegrind
    kdePackages.kcalc
    kdePackages.kcalendarcore
    kdePackages.kcalutils
    kdePackages.kcharselect
    kdePackages.kclock
    kdePackages.kcmutils
    kdePackages.kcodecs
    kdePackages.kcolorchooser
    kdePackages.kcolorpicker
    kdePackages.kcolorscheme
    kdePackages.kcompletion
    kdePackages.kconfig
    kdePackages.kconfigwidgets
    kdePackages.kcontacts
    kdePackages.kcoreaddons
    kdePackages.kcrash
    kdePackages.kcron
    kdePackages.kdav
    kdePackages.kdbusaddons
    kdePackages.kde-cli-tools
    kdePackages.kde-dev-scripts
    kdePackages.kde-dev-utils
    kdePackages.kde-gtk-config
    kdePackages.kde-inotify-survey
    kdePackages.kdebugsettings
    kdePackages.kdeclarative
    kdePackages.kdeconnect-kde
    kdePackages.kdecoration
    kdePackages.kded
    kdePackages.kdeedu-data
    kdePackages.kdegraphics-mobipocket
    kdePackages.kdegraphics-thumbnailers
    kdePackages.kdenetwork-filesharing
    kdePackages.kdenlive
    kdePackages.kdepim-addons
    kdePackages.kdepim-runtime
    kdePackages.kdeplasma-addons
    kdePackages.kdesdk-kio
    kdePackages.kdesdk-thumbnailers
    kdePackages.kdesu
    kdePackages.kdev-php
    kdePackages.kdev-python
    kdePackages.kdevelop
    kdePackages.kdevelop-pg-qt
    kdePackages.kdf
    kdePackages.kdiagram
    kdePackages.kdialog
    kdePackages.kdiamond
    kdePackages.kdnssd
    kdePackages.kdoctools
    kdePackages.kdsoap
    kdePackages.kdsoap-ws-discovery-client
    kdePackages.keditbookmarks
    kdePackages.keysmith
    kdePackages.kfilemetadata
    kdePackages.kfind
    kdePackages.kfourinline
    kdePackages.kgamma
    kdePackages.kgeography
    kdePackages.kget
    kdePackages.kglobalaccel
    kdePackages.kglobalacceld
    kdePackages.kgoldrunner
    kdePackages.kgpg
    kdePackages.kgraphviewer
    kdePackages.kguiaddons
    kdePackages.khangman
    kdePackages.khealthcertificate
    kdePackages.khelpcenter
    kdePackages.kholidays
    kdePackages.ki18n
    kdePackages.kiconthemes
    kdePackages.kidentitymanagement
    kdePackages.kidletime
    kdePackages.kigo
    kdePackages.killbots
    kdePackages.kimageannotator
    kdePackages.kimageformats
    kdePackages.kimagemapeditor
    kdePackages.kimap
    kdePackages.kinfocenter
    kdePackages.kio
    kdePackages.kio-admin
    kdePackages.kio-extras
    kdePackages.kio-extras-kf5
    kdePackages.kio-fuse
    kdePackages.kio-gdrive
    kdePackages.kio-zeroconf
    kdePackages.kirigami
    kdePackages.kirigami-addons
    kdePackages.kirigami-gallery
    kdePackages.kiriki
    kdePackages.kitemmodels
    kdePackages.kitemviews
    kdePackages.kiten
    kdePackages.kitinerary
    kdePackages.kjobwidgets
    kdePackages.kjournald
    kdePackages.kjumpingcube
    kdePackages.kldap
    kdePackages.kleopatra
    kdePackages.klettres
    kdePackages.klevernotes
    kdePackages.klickety
    kdePackages.klines
    kdePackages.kmag
    kdePackages.kmahjongg
    kdePackages.kmail
    kdePackages.kmail-account-wizard
    kdePackages.kmailtransport
    kdePackages.kmbox
    kdePackages.kmenuedit
    kdePackages.kmime
    kdePackages.kmines
    kdePackages.kmousetool
    kdePackages.kmouth
    kdePackages.kmplot
    kdePackages.knavalbattle
    kdePackages.knetwalk
    kdePackages.knewstuff
    kdePackages.knights
    kdePackages.knotifications
    kdePackages.knotifyconfig
    kdePackages.koi
    kdePackages.koko
    kdePackages.kolf
    kdePackages.kollision
    kdePackages.kolourpaint
    kdePackages.kompare
    kdePackages.kongress
    kdePackages.konquest
    kdePackages.konsole
    kdePackages.kontact
    kdePackages.kontactinterface
    kdePackages.kontrast
    kdePackages.konversation
    kdePackages.kopeninghours
    kdePackages.korganizer
    kdePackages.kosmindoormap
    kdePackages.kpackage
    kdePackages.kparts
    kdePackages.kpat
    kdePackages.kpeople
    kdePackages.kpimtextedit
    kdePackages.kpipewire
    kdePackages.kpkpass
    kdePackages.kplotting
    kdePackages.kpmcore
    kdePackages.kpty
    kdePackages.kpublictransport
    kdePackages.kquickcharts
    kdePackages.krdc
    kdePackages.krdp
    kdePackages.krecorder
    kdePackages.kreversi
    kdePackages.krfb
    kdePackages.krohnkite
    kdePackages.kruler
    kdePackages.krunner
    kdePackages.ksanecore
    kdePackages.kscreen
    kdePackages.kscreenlocker
    kdePackages.kservice
    kdePackages.kshisen
    kdePackages.ksirk
    kdePackages.ksmtp
    kdePackages.ksnakeduel
    kdePackages.kspaceduel
    kdePackages.ksquares
    kdePackages.ksshaskpass
    kdePackages.kstatusnotifieritem
    kdePackages.ksudoku
    kdePackages.ksvg
    kdePackages.ksystemlog
    kdePackages.ksystemstats
    kdePackages.kteatime
    kdePackages.ktextaddons
    kdePackages.ktexteditor
    kdePackages.ktexttemplate
    kdePackages.ktextwidgets
    kdePackages.ktimer
    kdePackages.ktnef
    kdePackages.ktorrent
    kdePackages.ktrip
    kdePackages.ktuberling
    kdePackages.kturtle
    kdePackages.kubrick
    kdePackages.kunifiedpush
    kdePackages.kunitconversion
    kdePackages.kup
    kdePackages.kuserfeedback
    kdePackages.kwallet
    kdePackages.kwallet-pam
    kdePackages.kwalletmanager
    kdePackages.kwayland
    kdePackages.kweather
    kdePackages.kweathercore
    kdePackages.kwidgetsaddons
    kdePackages.kwin
    kdePackages.kwindowsystem
    kdePackages.kwordquiz
    kdePackages.kwrited
    kdePackages.kxmlgui
    kdePackages.kzones
    kdePackages.layer-shell-qt
    kdePackages.libgravatar
    kdePackages.libkcddb
    kdePackages.libkcompactdisc
    kdePackages.libkdcraw
    kdePackages.libkdegames
    kdePackages.libkdepim
    kdePackages.libkeduvocdocument
    kdePackages.libkexiv2
    kdePackages.libkgapi
    kdePackages.libkleo
    kdePackages.libkmahjongg
    kdePackages.libkomparediff2
    kdePackages.libksane
    kdePackages.libkscreen
    kdePackages.libksieve
    kdePackages.libksysguard
    kdePackages.libktorrent
    kdePackages.libplasma
    kdePackages.lokalize
    kdePackages.lskat
    kdePackages.mailcommon
    kdePackages.mailimporter
    kdePackages.maplibre-native-qt
    kdePackages.markdownpart
    kdePackages.marknote
    kdePackages.massif-visualizer
    kdePackages.mbox-importer
    kdePackages.merkuro
    kdePackages.messagelib
    kdePackages.milou
    kdePackages.mimetreeparser
    kdePackages.minuet
    kdePackages.mlt
    kdePackages.modemmanager-qt
    kdePackages.networkmanager-qt
    kdePackages.ocean-sound-theme
    kdePackages.okular
    kdePackages.oxygen
    kdePackages.oxygen-icons
    kdePackages.oxygen-sounds
    kdePackages.packagekit-qt
    kdePackages.palapeli
    kdePackages.parley
    kdePackages.partitionmanager
    kdePackages.phonon
    kdePackages.phonon-vlc
    kdePackages.picmi
    kdePackages.pim-data-exporter
    kdePackages.pim-sieve-editor
    kdePackages.pimcommon
    kdePackages.plasma-activities
    kdePackages.plasma-activities-stats
    kdePackages.plasma-browser-integration
    kdePackages.plasma-desktop
    kdePackages.plasma-dialer
    kdePackages.plasma-disks
    kdePackages.plasma-firewall
    kdePackages.plasma-integration
    kdePackages.plasma-mobile
    kdePackages.plasma-nano
    kdePackages.plasma-nm
    kdePackages.plasma-pa
    kdePackages.plasma-sdk
    kdePackages.plasma-systemmonitor
    kdePackages.plasma-thunderbolt
    kdePackages.plasma-vault
    kdePackages.plasma-wayland-protocols
    kdePackages.plasma-welcome
    kdePackages.plasma-workspace
    kdePackages.plasma-workspace-wallpapers
    kdePackages.plasma5support
    kdePackages.plasmatube
    kdePackages.plymouth-kcm
    kdePackages.polkit-kde-agent-1
    kdePackages.polkit-qt-1
    kdePackages.poppler
    kdePackages.powerdevil
    kdePackages.poxml
    kdePackages.print-manager
    kdePackages.prison
    kdePackages.pulseaudio-qt
    kdePackages.purpose
    kdePackages.qca
    kdePackages.qcoro
    kdePackages.qgpgme
    kdePackages.qmake
    kdePackages.qmlbox2d
    kdePackages.qmlkonsole
    kdePackages.qqc2-breeze-style
    kdePackages.qqc2-desktop-style
    kdePackages.qscintilla
    kdePackages.qt3d
    kdePackages.qt5compat
    kdePackages.qt6ct
    kdePackages.qt6gtk2
    kdePackages.qtbase
    kdePackages.qtcharts
    kdePackages.qtconnectivity
    kdePackages.qtdatavis3d
    kdePackages.qtdeclarative
    kdePackages.qtdoc
    kdePackages.qtforkawesome
    kdePackages.qtgraphs
    kdePackages.qtgrpc
    kdePackages.qthttpserver
    kdePackages.qtimageformats
    kdePackages.qtkeychain
    kdePackages.qtlanguageserver
    kdePackages.qtlocation
    kdePackages.qtlottie
    kdePackages.qtmqtt
    kdePackages.qtmultimedia
    kdePackages.qtnetworkauth
    kdePackages.qtpbfimageplugin
    kdePackages.qtpositioning
    kdePackages.qtquick3d
    kdePackages.qtquick3dphysics
    kdePackages.qtquickeffectmaker
    kdePackages.qtquicktimeline
    kdePackages.qtremoteobjects
    kdePackages.qtscxml
    kdePackages.qtsensors
    kdePackages.qtserialbus
    kdePackages.qtserialport
    kdePackages.qtshadertools
    kdePackages.qtspeech
    kdePackages.qtstyleplugin-kvantum
    kdePackages.qtsvg
    kdePackages.qttools
    kdePackages.qttranslations
    kdePackages.qtutilities
    kdePackages.qtvirtualkeyboard
    kdePackages.qtwayland
    kdePackages.qtwebchannel
    kdePackages.qtwebengine
    kdePackages.qtwebsockets
    kdePackages.qtwebview
    kdePackages.quazip
    kdePackages.qwlroots
    kdePackages.qxlsx
    kdePackages.qzxing
    kdePackages.sddm
    kdePackages.sddm-kcm
    kdePackages.sierra-breeze-enhanced
    kdePackages.signon-kwallet-extension
    kdePackages.signond
    kdePackages.skanlite
    kdePackages.skanpage
    kdePackages.skladnik
    kdePackages.solid
    kdePackages.sonnet
    kdePackages.spacebar
    kdePackages.spectacle
    kdePackages.stdenv
    kdePackages.step
    kdePackages.svgpart
    kdePackages.sweeper
    kdePackages.syndication
    kdePackages.syntax-highlighting
    kdePackages.systemsettings
    kdePackages.taglib
    kdePackages.telly-skout
    kdePackages.threadweaver
    kdePackages.tokodon
    kdePackages.wacomtablet
    kdePackages.wayland
    kdePackages.wayland-protocols
    kdePackages.waylib
    kdePackages.wayqt
    kdePackages.wrapQtAppsHook
    kdePackages.wrapQtAppsNoGuiHook
    kdePackages.xdg-desktop-portal-kde
    kdePackages.xwaylandvideobridge
    kdePackages.yakuake
    kdePackages.zanshin
    kdePackages.zxing-cpp

    # Copy/paste from terminal
    wl-clipboard

    # For getting NixOS and Arch to play nicely together and vice versa
    arch-install-scripts

    # Development
    eclipses.eclipse-cpp
    gnumake

    # Important personal stuff
    openssl
    nss.tools
    pciutils
    nvme-cli
    hw-probe
    usbutils
    spotify
    libreoffice-fresh

    # Reproducibility
    nixos-install-tools

    # Pentesting, Part 1: General
    bat
    ranger
    discord-canary
    wordlists
    seclists
    freerdp3
    rlwrap
    mdbtools
    libpst

    # Pentesting, Part 2: Exploitation
    commix
    crackle
    exploitdb
    metasploit
    msfpc
#    routersploit # Build failure
    social-engineer-toolkit
    yersinia
    evil-winrm

    # Pentesting, Part 3: Forensics
    bulk_extractor
    capstone
    dc3dd
    ddrescue
    ext4magic
    extundelete
    ghidra-bin
    git
    p0f
    pdf-parser
    regripper
    sleuthkit

    # Pentesting, Part 4: Hardware
    apktool

    # Pentesting, Part 5: Reconnaisance
    cloudbrute
    dnsenum
    adreaper
    openldap
    ldeep
    linux-exploit-suggester
    dnsrecon
    enum4linux
    hping
    masscan
    netcat
    nmap
    ntopng
    sn0int
    sslsplit
    theharvester
    wireshark
    smbmap

    # Pentesting, Part 6: Python
    (python3.withPackages(pypkgs: [
#      pypkgs.binwalk-full # Removed from repositories
#      pypkgs.distorm3     # NixOS/nixpkgs#328346
      pypkgs.requests
      pypkgs.beautifulsoup4
      pypkgs.pygobject3
      pypkgs.scapy
      pypkgs.impacket
      pypkgs.xsser
      pypkgs.pypykatz
    ]))

    # Pentesting, Part 7: Pivoting
    httptunnel
    pwnat
    ligolo-ng

    # Pentesting, Part 8: Brute Force
    brutespray
    cewl
    chntpw
#     crowbar # Build failure
    crunch
    hashcat
    hashcat-utils
    hash-identifier
    hcxtools
    john
    phrasendrescher
    thc-hydra
    netexec
    medusa
    kerbrute
    responder

    # Pentesting, Part 9: Disassemblers
    binutils
    elfutils
    bytecode-viewer
    patchelf
    radare2
    # cutter Build failure
    retdec
    snowman
    valgrind
    yara

    # Pentesting, Part 10: Packet Sniffers
    bettercap
    dsniff
    mitmproxy
    rshijack
    sipp
    sniffglue
    sslstrip

    # Pentesting, Part 11: Vulnerability Analyzers
    grype
    lynis
    sqlmap
    vulnix
    whatweb

    # Pentesting, Part 12: Web Attack Tools
    wafw00f
    dirb
    gobuster
    urlhunter
    python311Packages.wfuzz
    zap
    burpsuite
    ffuf
    whatweb
    wpscan
    nikto

    # Pentesting, Part 13: Wi-Fi
    aircrack-ng
    asleap
    bully
    cowpatty
    gqrx
    kalibrate-hackrf
    kalibrate-rtl
    killerbee
    kismet
    mfcuk
    mfoc
    multimon-ng
    redfang
    wifite2
    wirelesstools

    # Custom packages, Part 1: PwnXSS
    (pkgs.stdenv.mkDerivation rec {
      pname = "pwnxss";
      version = "0.5.0";

      format = "pyproject";

      src = builtins.fetchGit {
        url = "https://github.com/Pwn0Sec/PwnXSS";
        ref = "master";
      };

      propagatedBuildInputs = [
        (python311.withPackages(pypkgs: [
          pypkgs.wrapPython
          pypkgs.beautifulsoup4
          pypkgs.requests
        ]))
      ];

      buildInputs = propagatedBuildInputs;
      nativeBuildInputs = propagatedBuildInputs;

      pythonPath = with python3Packages; [ beautifulsoup4 requests ];

      pwnxssExecutable = placeholder "out" + "/bin/pwnxss";

      installPhase = ''
        # Base directories
        install -dm755 $out/share/pwnxss
        install -dm755 $out/bin

        # Copy files
        cp -a --no-preserve=ownership * "$out/share/pwnxss"

        # Use wrapper script to allow execution from anywhere
        cat > $out/bin/pwnxss << EOF
        #!${pkgs.bash}/bin/bash
        cd $out/share/pwnxss
        python pwnxss.py \$@
        EOF

        chmod a+x $out/bin/pwnxss
      '';
    })

    # Custom packages, Part 2: CUPP
    (pkgs.stdenv.mkDerivation rec {
      pname = "cupp";
      version = "3.2.0-alpha";

      src = builtins.fetchGit {
        url = "https://github.com/Mebus/cupp";
        ref = "master";
      };

      installPhase = ''
        # Base directories
        install -dm755 $out/share/cupp
        install -dm755 $out/bin

        # Copy files
        cp -a --no-preserve=ownership * "$out/share/cupp"

        # Use wrapper script to allow execution from anywhere
        cat > $out/bin/cupp << EOF
        #!${pkgs.bash}/bin/bash
        cd $out/share/cupp
        python cupp.py \$@
        EOF

        chmod a+x $out/bin/cupp
      '';
    })
  ];

"""

cfgtail = """  # PAM configuration
  security.pam = {
    # KWallet auto-unlock
    services.sddm.enableKwallet = true;
  };

  # Flatpak
  services.flatpak.enable = true;

  # Keep system up-to-date without intervention
  system.autoUpgrade = {
    enable = true;
    channel = "nixos";
    dates = "03:00";
    rebootWindow.lower = "01:00";
    rebootWindow.upper = "05:00";
    persistent = true;
  };

  # Collect garbage after each automatic update
  systemd.services."nixos-upgrade".postStart = "${pkgs.nix}/bin/nix-collect-garbage -d";

  # Memory compression
  zramSwap = {
    enable = true;
    algorithm = "zstd";
    memoryPercent = 300;
  };

  # System-wide shell config
  environment.etc.bashrc.text = ''
    # Create /opt if it doesn't already exist and set proper permissions on it
    if [ ! -d /opt ]; then
      if [ $UID -eq 0 ]; then
        mkdir /opt
        chmod -R a+rw /opt
      else
        sudo mkdir /opt
        sudo chmod -R a+rw /opt
      fi
    fi

    # Ensure that Rust is installed in the correct (sysmtem-wide) location
    export CARGO_BUILD_JOBS=$(nproc)
    export RUSTUP_HOME=/opt/rust
    export CARGO_HOME=/opt/rust

    # Add Rust to $PATH if installed
    if [ -f /opt/rust/env ]; then
      source /opt/rust/env
    elif [ -d /opt/rust/bin ]; then
      export PATH=/opt/rust/bin:$PATH
    fi

    # Allow editing of files as root
    alias pkexec="pkexec env DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY KDE_SESSION_VERSION=6 KDE_FULL_SESSION=true"

    #PwnBox-style shell prompt
    PS1="\[\033[1;32m\]\342\224\214\342\224\200\$([[ \$(/etc/htb/vpnbash.sh) == *\"10.\"* ]] && echo \"[\[\033[1;34m\]\$(/etc/htb/vpnserver.sh)\[\033[1;32m\]]\342\224\200[\[\033[1;37m\]\$(/etc/htb/vpnbash.sh)\[\033[1;32m\]]\342\224\200\")[\[\033[1;37m\]\u\[\033[01;32m\]@\[\033[01;34m\]\h\[\033[1;32m\]]\342\224\200[\[\033[1;37m\]\w\[\033[1;32m\]]\n\[\033[1;32m\]\342\224\224\342\224\200\342\224\200\342\225\274 [\[\e[01;33m\]★\[\e[01;32m\]]\\$ \[\e[0m\]"

    # Fix Internet connection
    if [ "$(ip link | grep enp4s0 | cut -d' ' -f9)" == "DOWN" ]
    then
      connection=$(nmcli c show | grep enp4s0 | cut -d' ' -f1)

      sudo ip link set dev enp4s0 up
      nmcli c "$connection" up

      while [ $? -ne 0 ]
      do
        sudo ip link set dev enp4s0 up
        nmcli c "$connection" up
      done
    fi

    # Alias BeEF to start script
    alias beef="${config.systemd.services."docker-beef".serviceConfig."ExecStart"}"

    # Make upgrades easier
    alias parrot-upgrade="sudo nixos-rebuild switch --upgrade && sudo nix-collect-garbage -d"
    alias nixos-upgrade="sudo nixos-rebuild switch --upgrade && sudo nix-collect-garbage -d"

    # Impacket aliases to ease transition from Parrot/Kali
    for script in ${pkgs.python3Packages.impacket}/bin/*
    do
      alias impacket-$(echo $script | cut -d'/' -f6 | cut -d'.' -f1)="$script"
    done

    # Make it easier to use arrow keys inside reverse shells
    alias nc="sudo rlwrap ncat"
  '';

  # VPN connection name
  environment.etc."htb/vpnserver.sh".text = ''
    #!${pkgs.bash}/bin/bash

    nmcli c show | grep vpn | grep academy | cut -d' ' -f1
  '';

  # VPN IP address
  environment.etc."htb/vpnbash.sh".text = ''
    #!${pkgs.bash}/bin/bash
    htbip=$(ip addr | grep tun | grep inet | grep -E "(10\.10|10\.129)" | tr -s " " | cut -d " " -f 3 | cut -d "/" -f 1)

    if [[ $htbip == *"10."* ]]
    then
       echo "$htbip"
    else
       echo "No VPN"
    fi
  '';

  environment.etc."htb/vpnserver.sh".mode = "0755";
  environment.etc."htb/vpnbash.sh".mode = "0755";

  # Keep USB mice and keyboards awake at all times
  services.udev.extraRules = ''
    ACTION=="add", SUBSYSTEM=="usb", TEST=="power/control", ATTR{power/control}="on"
    ACTION=="add", SUBSYSTEM=="usb", TEST=="power/autosuspend", ATTR{power/autosuspend}="0"
    ACTION=="add", SUBSYSTEM=="usb", TEST=="power/autosuspend_delay_ms", ATTR{power/autosuspend_delay_ms}="0"
  '';

  # Some programs need SUID wrappers, can be configured further or are
  # started in user sessions.
  # programs.mtr.enable = true;
  # programs.gnupg.agent = {
  #   enable = true;
  #   enableSSHSupport = true;
  # };

  # Open ports in the firewall.
  networking = {
    firewall = {
        # This breaks pentest tools, so need to disable
        enable = false;
#         allowPing = false;
#         allowedUDPPorts = [ 80 443 4822 57621 ];
#         allowedTCPPorts = [ 22 80 443 4822 5353 ];
    };
    extraHosts = ''
      # Suspicious TLDs
      0.0.0.0 (^|\.)(cn|ir|zip|mov)$
    '';
    nftables.enable = false;
  };

  # User-level config
  home-manager = {

    backupFileExtension = "old";
    useGlobalPkgs = true;

    users."${systemUser}" = { stdenv, fetchurl, lib, pkgs, ... }: {
      home.stateVersion = config.system.stateVersion;

      imports = [
        (import "${plasma-manager}/modules")
      ];

      services.home-manager.autoUpgrade.enable = config.system.autoUpgrade.enable;
      services.home-manager.autoUpgrade.frequency = config.system.autoUpgrade.dates;

      programs.konsole = {
        enable = true;
        defaultProfile = "HTB";
        profiles."HTB" = {

          font = {
            name = "Monospace";
            size = 12;
          };

          extraConfig = {
            Appearance = {
              ColorScheme = "GreenOnBlack";
            };

            General = {
              TerminalColumns = 117;
              TerminalRows = 35;
            };
          };
        };
      };

      programs.plasma = {
        enable = true;

        #
        # Some high-level settings:
        #
        workspace = {
          lookAndFeel = "org.kde.breezedark.desktop";
          wallpaper = desktopBackground;
        };

        hotkeys.commands."launch-konsole" = {
          name = "Launch Konsole";
          key = "Ctrl+Alt+T";
          command = "konsole";
        };

        input.mice =  [
          {
            acceleration = 1.0;
            accelerationProfile = "none";
            name = builtins.readFile (pkgs.runCommand "mousename" { } "grep -B1 -A9 'Mouse' /proc/bus/input/devices | grep 'Name' | cut -d\= -f2 | cut -d'\"' -f2 > $out");
            vendorId = builtins.readFile (pkgs.runCommand "vendor" { } "grep -B1 -A9 'Mouse' /proc/bus/input/devices | grep 'I:' | tr ' ' '\n' | grep -v 'I:' | grep -v 'Bus' | grep -v 'Version' | cut -d\= -f2 | head -n1 | tr -d '\n' > $out");
            productId = builtins.readFile (pkgs.runCommand "product" { } "grep -B1 -A9 'Mouse' /proc/bus/input/devices | grep 'I:' | tr ' ' '\n' | grep -v 'I:' | grep -v 'Bus' | grep -v 'Version' | cut -d\= -f2 | tail -n1 | tr -d '\n' > $out");
          }
        ];

        panels = [

          # Bottom panel: MacOS-like dock
          {
            location = "bottom";
            height = 64;
            floating = true;
            alignment = "center";
            lengthMode = "fit";
            widgets = [
              #
              {
                iconTasks = {
                  launchers = [
                    "applications:systemsettings.desktop"
                    "applications:org.kde.discover.desktop"
                    "applications:org.kde.dolphin.desktop"
                    "applications:org.kde.konsole.desktop"
                    "applications:google-chrome.desktop"
                    "applications:org.kde.kate.desktop"
                    "applications:code.desktop"
                    "applications:Eclipse.desktop"
                    "applications:discord-canary.desktop"
                    "applications:burpsuite.desktop"
                    "applications:zap.desktop"
                  ];
                };
              }
            ];
            hiding = "none";
          }

          # Top panel: Kickoff, app name, global menu, system tray
          {
            location = "top";
            height = 32;
            floating = true;
            widgets = [
              {
                name = "org.kde.plasma.kickoff";
                config = {
                  General = {
                    icon = launcherIcon;
                    alphaSort = true;
                  };
                };
              }
              {
                applicationTitleBar = {
                  behavior = {
                    activeTaskSource = "activeTask";
                  };
                  layout = {
                    elements = [ "windowTitle" ];
                    horizontalAlignment = "left";
                    showDisabledElements = "deactivated";
                    verticalAlignment = "center";
                  };
                  overrideForMaximized.enable = false;
                  titleReplacements = [
                    {
                      type = "regexp";
                      originalTitle = "^Brave Web Browser$";
                      newTitle = "Brave";
                    }
                    {
                      type = "regexp";
                      originalTitle = ''\\bDolphin\\b'';
                      newTitle = "File Manager";
                    }
                  ];
                  windowTitle = {
                    font = {
                      bold = true;
                      fit = "fixedSize";
                      size = 12;
                    };
                    hideEmptyTitle = true;
                    margins = {
                      bottom = 0;
                      left = 10;
                      right = 5;
                      top = 0;
                    };
                    source = "appName";
                  };
                };
              }
              "org.kde.plasma.appmenu"
              "org.kde.plasma.panelspacer"
              {
                digitalClock = {
                  date.enable = false;
                  calendar.firstDayOfWeek = "sunday";
                  time = {
                    format = "24h";
                    showSeconds = "always";
                  };
                };
              }
              "org.kde.plasma.panelspacer"
              {
                systemTray.items = {
                  shown = [
                    "org.kde.plasma.battery"
                    "org.kde.plasma.bluetooth"
                    "org.kde.plasma.networkmanagement"
                    "org.kde.plasma.volume"
                  ];
                };
              }
            ];
          }
        ];

        powerdevil = {
          AC = {
            powerButtonAction = "shutDown";
            autoSuspend = {
              action = "nothing";
            };
            turnOffDisplay = {
              idleTimeout = "never";
            };
            dimDisplay = {
              enable = false;
            };
            displayBrightness = 100;
            powerProfile = "performance";
          };

          battery = {
            powerButtonAction = "sleep";
            whenSleepingEnter = "standbyThenHibernate";
          };
          lowBattery = {
            whenLaptopLidClosed = "hibernate";
          };
        };

        kscreenlocker = {
          autoLock = false;
          lockOnResume = false;
          lockOnStartup = false;
          timeout = null;
        };

        #
        # Some mid-level settings:
        #
        shortcuts = {
          ksmserver = {
            "Lock Session" = [
              "Screensaver"
              "Meta+Ctrl+Alt+L"
            ];
          };

          kwin = {
            "Expose" = "Meta+,";
            "Switch Window Down" = "Meta+J";
            "Switch Window Left" = "Meta+H";
            "Switch Window Right" = "Meta+L";
            "Switch Window Up" = "Meta+K";
          };
        };
      };
    };
  };

  system.stateVersion = "@@nixosversion@@";
}
"""
def env_is_set(name):
    envValue = os.environ.get(name)
    return not (envValue is None or envValue == "")

def generateProxyStrings():
    proxyEnv = []
    if env_is_set('http_proxy'):
        proxyEnv.append('http_proxy={}'.format(os.environ.get('http_proxy')))
    if env_is_set('https_proxy'):
        proxyEnv.append('https_proxy={}'.format(os.environ.get('https_proxy')))
    if env_is_set('HTTP_PROXY'):
        proxyEnv.append('HTTP_PROXY={}'.format(os.environ.get('HTTP_PROXY')))
    if env_is_set('HTTPS_PROXY'):
        proxyEnv.append('HTTPS_PROXY={}'.format(os.environ.get('HTTPS_PROXY')))

    if len(proxyEnv) > 0:
        proxyEnv.insert(0, "env")

    return proxyEnv

def pretty_name():
    return _("Installing NixOS.")


status = pretty_name()


def pretty_status_message():
    return status


def catenate(d, key, *values):
    """
    Sets @p d[key] to the string-concatenation of @p values
    if none of the values are None.
    This can be used to set keys conditionally based on
    the values being found.
    """
    if [v for v in values if v is None]:
        return

    d[key] = "".join(values)


def run():
    """NixOS Configuration."""

    global status
    status = _("Configuring NixOS")
    libcalamares.job.setprogress(0.1)

    # Create initial config file
    cfg = cfghead
    gs = libcalamares.globalstorage
    variables = dict()

    # Setup variables
    root_mount_point = gs.value("rootMountPoint")
    config = os.path.join(root_mount_point, "etc/nixos/configuration.nix")
    fw_type = gs.value("firmwareType")
    bootdev = (
        "nodev"
        if gs.value("bootLoader") is None
        else gs.value("bootLoader")["installPath"]
    )

    # Pick config parts and prepare substitution

    # Check bootloader
    if fw_type == "efi":
        cfg += cfgbootefi
    elif bootdev != "nodev":
        cfg += cfgbootbios
        catenate(variables, "bootdev", bootdev)
    else:
        cfg += cfgbootnone

    # Setup encrypted swap devices. nixos-generate-config doesn't seem to notice them.
    for part in gs.value("partitions"):
        if (
            part["claimed"] is True
            and (part["fsName"] == "luks" or part["fsName"] == "luks2")
            and part["device"] is not None
            and part["fs"] == "linuxswap"
        ):
            cfg += """  boot.initrd.luks.devices."{}".device = "/dev/disk/by-uuid/{}";\n""".format(
                part["luksMapperName"], part["uuid"]
            )

    # Check partitions
    root_is_encrypted = False
    boot_is_encrypted = False
    boot_is_partition = False

    for part in gs.value("partitions"):
        if part["mountPoint"] == "/":
            root_is_encrypted = part["fsName"] in ["luks", "luks2"]
        elif part["mountPoint"] == "/boot":
            boot_is_partition = True
            boot_is_encrypted = part["fsName"] in ["luks", "luks2"]

    # Setup keys in /boot/crypto_keyfile if using BIOS and Grub cryptodisk
    if fw_type != "efi" and (
        (boot_is_partition and boot_is_encrypted)
        or (root_is_encrypted and not boot_is_partition)
    ):
        cfg += cfgbootgrubcrypt
        status = _("Setting up LUKS")
        libcalamares.job.setprogress(0.15)
        try:
            libcalamares.utils.host_env_process_output(
                ["mkdir", "-p", root_mount_point + "/boot"], None
            )
            libcalamares.utils.host_env_process_output(
                ["chmod", "0700", root_mount_point + "/boot"], None
            )
            # Create /boot/crypto_keyfile.bin
            libcalamares.utils.host_env_process_output(
                [
                    "dd",
                    "bs=512",
                    "count=4",
                    "if=/dev/random",
                    "of=" + root_mount_point + "/boot/crypto_keyfile.bin",
                    "iflag=fullblock",
                ],
                None,
            )
            libcalamares.utils.host_env_process_output(
                ["chmod", "600", root_mount_point + "/boot/crypto_keyfile.bin"], None
            )
        except subprocess.CalledProcessError:
            libcalamares.utils.error("Failed to create /boot/crypto_keyfile.bin")
            return (
                _("Failed to create /boot/crypto_keyfile.bin"),
                _("Check if you have enough free space on your partition."),
            )

        for part in gs.value("partitions"):
            if (
                part["claimed"] is True
                and (part["fsName"] == "luks" or part["fsName"] == "luks2")
                and part["device"] is not None
            ):
                cfg += """  boot.initrd.luks.devices."{}".keyFile = "/boot/crypto_keyfile.bin";\n""".format(
                    part["luksMapperName"]
                )
                try:
                    # Grub currently only supports pbkdf2 for luks2
                    libcalamares.utils.host_env_process_output(
                        [
                            "cryptsetup",
                            "luksConvertKey",
                            "--hash",
                            "sha256",
                            "--pbkdf",
                            "pbkdf2",
                            part["device"],
                        ],
                        None,
                        part["luksPassphrase"],
                    )
                    # Add luks drives to /boot/crypto_keyfile.bin
                    libcalamares.utils.host_env_process_output(
                        [
                            "cryptsetup",
                            "luksAddKey",
                            "--hash",
                            "sha256",
                            "--pbkdf",
                            "pbkdf2",
                            part["device"],
                            root_mount_point + "/boot/crypto_keyfile.bin",
                        ],
                        None,
                        part["luksPassphrase"],
                    )
                except subprocess.CalledProcessError:
                    libcalamares.utils.error(
                        "Failed to add {} to /boot/crypto_keyfile.bin".format(
                            part["luksMapperName"]
                        )
                    )
                    return (
                        _("cryptsetup failed"),
                        _(
                            "Failed to add {} to /boot/crypto_keyfile.bin".format(
                                part["luksMapperName"]
                            )
                        ),
                    )

    status = _("Configuring NixOS")
    libcalamares.job.setprogress(0.18)

    cfg += cfgnetwork
    cfg += cfgnetworkmanager

    if gs.value("hostname") is None:
        catenate(variables, "hostname", "nixos")
    else:
        catenate(variables, "hostname", gs.value("hostname"))

    if gs.value("locationRegion") is not None and gs.value("locationZone") is not None:
        cfg += cfgtime
        catenate(
            variables,
            "timezone",
            gs.value("locationRegion"),
            "/",
            gs.value("locationZone"),
        )

    if gs.value("localeConf") is not None:
        localeconf = gs.value("localeConf")
        locale = localeconf.pop("LANG").split("/")[0]
        cfg += cfglocale
        catenate(variables, "LANG", locale)
        if (
            len(set(localeconf.values())) != 1
            or list(set(localeconf.values()))[0] != locale
        ):
            cfg += cfglocaleextra
            for conf in localeconf:
                catenate(variables, conf, localeconf.get(conf).split("/")[0])

    # Choose desktop environment
    cfg += cfgplasma6

    if (
        gs.value("keyboardLayout") is not None
        and gs.value("keyboardVariant") is not None
    ):
        cfg += cfgkeymap
        catenate(variables, "kblayout", gs.value("keyboardLayout"))
        catenate(variables, "kbvariant", gs.value("keyboardVariant"))

        if gs.value("keyboardVConsoleKeymap") is not None:
            try:
                subprocess.check_output(
                    ["pkexec", "loadkeys", gs.value("keyboardVConsoleKeymap").strip()],
                    stderr=subprocess.STDOUT,
                )
                cfg += cfgconsole
                catenate(
                    variables, "vconsole", gs.value("keyboardVConsoleKeymap").strip()
                )
            except subprocess.CalledProcessError as e:
                libcalamares.utils.error("loadkeys: {}".format(e.output))
                libcalamares.utils.error(
                    "Setting vconsole keymap to {} will fail, using default".format(
                        gs.value("keyboardVConsoleKeymap").strip()
                    )
                )
        else:
            kbdmodelmap = open(
                "/run/current-system/sw/share/systemd/kbd-model-map", "r"
            )
            kbd = kbdmodelmap.readlines()
            out = []
            for line in kbd:
                if line.startswith("#"):
                    continue
                out.append(line.split())
            # Find rows with same layout
            find = []
            for row in out:
                if gs.value("keyboardLayout") == row[1]:
                    find.append(row)
            if find != []:
                vconsole = find[0][0]
            else:
                vconsole = ""
            if gs.value("keyboardVariant") is not None:
                variant = gs.value("keyboardVariant")
            else:
                variant = "-"
            # Find rows with same variant
            for row in find:
                if variant in row[3]:
                    vconsole = row[0]
                    break
                # If none found set to "us"
            if vconsole != "" and vconsole != "us" and vconsole is not None:
                try:
                    subprocess.check_output(
                        ["pkexec", "loadkeys", vconsole], stderr=subprocess.STDOUT
                    )
                    cfg += cfgconsole
                    catenate(variables, "vconsole", vconsole)
                except subprocess.CalledProcessError as e:
                    libcalamares.utils.error("loadkeys: {}".format(e.output))
                    libcalamares.utils.error("vconsole value: {}".format(vconsole))
                    libcalamares.utils.error(
                        "Setting vconsole keymap to {} will fail, using default".format(
                            gs.value("keyboardVConsoleKeymap")
                        )
                    )

    cfg += cfgmisc

    if gs.value("username") is not None:
        fullname = gs.value("fullname")
        groups = ["networkmanager", "wheel"]

        cfg += cfgusers
        catenate(variables, "username", gs.value("username"))
        catenate(variables, "fullname", fullname)
        catenate(variables, "groups", (" ").join(['"' + s + '"' for s in groups]))
        if (
            gs.value("autoLoginUser") is not None
            and gs.value("packagechooser_packagechooser") is not None
            and gs.value("packagechooser_packagechooser") != ""
        ):
            cfg += cfgautologin
            if gs.value("packagechooser_packagechooser") == "gnome":
                cfg += cfgautologingdm
        elif gs.value("autoLoginUser") is not None:
            cfg += cfgautologintty

    cfg += cfgpkgs
    cfg += cfgtail
    
    version = ".".join(subprocess.getoutput(["nixos-version"]).split(".")[:2])[:5]
    catenate(variables, "nixosversion", version)

    # Check that all variables are used
    for key in variables.keys():
        pattern = "@@{key}@@".format(key=key)
        if pattern not in cfg:
            libcalamares.utils.warning("Variable '{key}' is not used.".format(key=key))

    # Check that all patterns exist
    variable_pattern = re.compile(r"@@\w+@@")
    for match in variable_pattern.finditer(cfg):
        variable_name = cfg[match.start() + 2 : match.end() - 2]
        if variable_name not in variables:
            libcalamares.utils.warning(
                "Variable '{key}' is used but not defined.".format(key=variable_name)
            )

    # Do the substitutions
    for key in variables.keys():
        pattern = "@@{key}@@".format(key=key)
        cfg = cfg.replace(pattern, str(variables[key]))

    status = _("Generating NixOS configuration")
    libcalamares.job.setprogress(0.25)

    try:
        # Generate hardware.nix with mounted swap device
        subprocess.check_output(
            ["pkexec", "nixos-generate-config", "--root", root_mount_point],
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as e:
        if e.output is not None:
            libcalamares.utils.error(e.output.decode("utf8"))
        return (_("nixos-generate-config failed"), _(e.output.decode("utf8")))

    # Check for unfree stuff in hardware-configuration.nix
    hf = open(root_mount_point + "/etc/nixos/hardware-configuration.nix", "r")
    htxt = hf.read()
    search = re.search(r"boot\.extraModulePackages = \[ (.*) \];", htxt)

    # Check if any extraModulePackages are defined, and remove if only free packages are allowed
    if search is not None and free:
        expkgs = search.group(1).split(" ")
        for pkg in expkgs:
            p = ".".join(pkg.split(".")[3:])
            # Check package p is unfree
            isunfree = subprocess.check_output(
                [
                    "nix-instantiate",
                    "--eval",
                    "--strict",
                    "-E",
                    "with import <nixpkgs> {{}}; pkgs.linuxKernel.packageAliases.linux_default.{}.meta.unfree".format(
                        p
                    ),
                    "--json",
                ],
                stderr=subprocess.STDOUT,
            )
            if isunfree == b"true":
                libcalamares.utils.warning(
                    "{} is marked as unfree, removing from hardware-configuration.nix".format(
                        p
                    )
                )
                expkgs.remove(pkg)
        hardwareout = re.sub(
            r"boot\.extraModulePackages = \[ (.*) \];",
            "boot.extraModulePackages = [ {}];".format(
                "".join(map(lambda x: x + " ", expkgs))
            ),
            htxt,
        )
        # Write the hardware-configuration.nix file
        libcalamares.utils.host_env_process_output(
            [
                "cp",
                "/dev/stdin",
                root_mount_point + "/etc/nixos/hardware-configuration.nix",
            ],
            None,
            hardwareout,
        )

    # Write the configuration.nix file
    libcalamares.utils.host_env_process_output(["cp", "/dev/stdin", config], None, cfg)

    status = _("Installing NixOS")
    libcalamares.job.setprogress(0.3)

    # build nixos-install command
    nixosInstallCmd = [ "pkexec" ]
    nixosInstallCmd.extend(generateProxyStrings())
    nixosInstallCmd.extend(
        [
            "nixos-install",
            "--no-root-passwd",
            "--root",
            root_mount_point
        ]
    )

    # Install customizations
    try:
        output = ""
        proc = subprocess.Popen(
            nixosInstallCmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        while True:
            line = proc.stdout.readline().decode("utf-8")
            output += line
            libcalamares.utils.debug("nixos-install: {}".format(line.strip()))
            if not line:
                break
        exit = proc.wait()
        if exit != 0:
            return (_("nixos-install failed"), _(output))
    except:
        return (_("nixos-install failed"), _("Installation failed to complete"))

    return None
