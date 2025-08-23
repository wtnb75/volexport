# volexport: API server for creating and exporting LVM2 volumes via iSCSI

## Overview

`volexport` is an API server that provides management functions for LVM2 volumes and exposes them via iSCSI. It allows you to create and delete LVM2 logical volumes, as well as publish volumes over iSCSI for remote access.

## Features

- Create LVM2 logical volumes
- Delete LVM2 logical volumes
- Publish volumes via iSCSI
- RESTful API interface: [API spec](https://wtnb75.github.io/volexport/api/)

## Installation

- Requirements
    - LVM2, VG created
    - [tgtd](https://github.com/fujita/tgt)
        - alpine: `apk add scsi-tgt`
        - ubuntu: `apt install tgt`
        - archlinux: `pacman -Sy extra/tgt`
- pip install volexport

## Boot

```plaintext
Usage: volexport server [OPTIONS]

  Run the volexport server.

Options:
  --verbose / --quiet   log level
  --become-method TEXT  sudo/doas/runas, etc...
  --tgtadm-bin TEXT     tgtadm command
  --tgt-bstype TEXT     backing store type
  --tgt-bsopts TEXT     bs options
  --tgt-bsoflags TEXT   bs open flags
  --lvm-bin TEXT        lvm command
  --nics TEXT           use interfaces
  --iqn-base TEXT       iSCSI target basename
  --vg TEXT             LVM volume group
  --host TEXT           listen host
  --port INTEGER        listen port
  --log-config PATH     uvicorn log config
  --cmd-timeout FLOAT   command execution timeout
  --help                Show this message and exit.
```

- `volexport server [OPTIONS]`

## Examples
