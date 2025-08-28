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

## Examples (curl)

prepare

- `endpoint=http://volexport-api:8080/`

create volume and mount

- create volume (name=vol123, size=100GB)
    - `curl --json $(jo name=vol123 size=107374182400) ${endpoint}/volume`
- export volume
    - `curl --json $(jo volname=vol123 acl=$(jo -a 192.168.104.0/24)) ${endpoint}/export`
    - ```json
      {
        "protocol": "iscsi",
        "addresses": [
            "192.168.104.1:3260"
        ],
        "targetname": "iqn.2025-08.com.github.wtnb75:6688f7a2585ef52a139b",
        "tid": 1,
        "user": "user123",
        "passwd": "passwd123",
        "lun": 1,
        "acl": [
            "192.168.104.0/24"
        ]
      }
      ```
    - `target=iqn.2025-08.com.github.wtnb75:6688f7a2585ef52a139b`
- attach
    - `iscsiadm -m discovery -t st -p 192.168.104.1:3260`
    - `iscsiadm -m node -T ${target} -o update -n node.session.auth.authmethod -v CHAP`
    - `iscsiadm -m node -T ${target} -o update -n node.session.auth.username -v user123`
    - `iscsiadm -m node -T ${target} -o update -n node.session.auth.password -v passwd123`
    - `iscsiadm -m node -T ${target} -l`
    - `iscsiadm -m session -P 3`
        - shows device name at last line
- mkfs
    - `mkfs /dev/(device name)`
- mount
    - `mount /dev/(device name) (mount point)`

enlarge volume

- resize volume(100GB -> 200GB)
    - `curl --json $(jo size=214748364800) ${endpoint}/volume/vol123`
- apply new size
    - `iscsiadm -m node -T ${target} -R`
- resize filesystem
    - `resize2fs /dev/(device name)`

shrink volume

- umount
    - `umount (mount point)`
- resize filesystem
    - `e2fsck -f /dev/(device name)`
    - `resize2fs /dev/(device name) 50G`
- mount
    - `mount /dev/(device name) (mount point)`
- resize volume(-> 50GB)
    - `curl --json $(jo size=53687091200) ${endpoint}/volume/vol123`
- apply new size
    - `iscsiadm -m node -T ${target} -R`

umount and detach

- umount
    - `umount /dev/(device name)`
- detach
    - `iscsiadm -m node -T ${target} -u`
- remove discovery
    - `iscsiadm -m discoverydb -t st -p 192.168.104.1:3260 --op delete`

unexport and delete volume

- unexport
    - `curl -XDELETE ${endpoint}/export/${target}`
- delete volume
    - `curl -XDELETE ${endpoint}/volume/vol123`

## Examples (internal REST client)

prepare

- `export VOLEXP_ENDPOINT=http://volexport-api:8080/`

create volume and mount

- create volume (name=vol123, size=100GB)
    - `volexp-client volume-create --name vol123 --size 100G`
- mkfs volume
    - `volexp-client volume-mkfs --name vol123 --filesystem ext4`
- export volume
    - `volexp-client export-create --name vol123`
- attach
    - copy and paste, execute commands
    - ```
      iscsiadm -m discovery -t st -p 192.168.104.1:3260
      iscsiadm -m node -T iqn.xxxx:yyyy -o update -n node.session.auth.authmethod -v CHAP
      iscsiadm -m node -T iqn.xxxx:yyyy -o update -n node.session.auth.username -v user123
      iscsiadm -m node -T iqn.xxxx:yyyy -o update -n node.session.auth.password -v passwd123
      iscsiadm -m node -T iqn.xxxx:yyyy -l
      ```
    - `iscsiadm -m session -P 3`
        - shows device name at last line
    - volume label if mkfs'ed: `lsblk -f`, `blkid`, etc...
