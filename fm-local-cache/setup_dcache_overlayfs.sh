#!/bin/bash

DUNE_WORKDIR="${HOME}/dune_workdir"
NFS_SERVER="fm-nfs-server.bluerock.nf"
NFS_SHARE="/var/cache/rsync_fm_cache/"
MOUNT_POINT="${DUNE_WORKDIR}/dune_nfs"
UPPER_DIR="${DUNE_WORKDIR}/nfs_upper"
WORK_DIR="${DUNE_WORKDIR}/nfs_work"
MERGED_DIR="${DUNE_WORKDIR}/nfs_merged"

create_workdirs() {
  echo "Creating required directories..."
  mkdir -p "$MOUNT_POINT" "$UPPER_DIR" "$WORK_DIR" "$MERGED_DIR"
}

check_dune_nfs_status() {
    if mount | grep -q "$MOUNT_POINT"; then
        echo "Dune NFS cache is mounted at $MOUNT_POINT"
    else
        echo "Dune NFS cache is not mounted at $MOUNT_POINT"
    fi
}

check_overlayfs_status() {
  if mount | grep -q "on $MERGED_DIR type overlay"; then
    echo "OverlayFS is mounted on $MERGED_DIR"
  else
    echo "OverlayFS is not mounted on $MERGED_DIR"
  fi
}

mount_dune_nfs() {
  echo "Mounting NFS share as read-only..."
  echo "Requires sudo privileges to mount NFS partition..."
  sudo mount -t nfs -o ro $NFS_SERVER:$NFS_SHARE "$MOUNT_POINT"
 }

umount_dune_nfs() {
  echo "Unmounting NFS share from $MOUNT_POINT..."
  sudo umount "$MOUNT_POINT"
}

umount_overlayfs() {
  if ! check_overlayfs_status | grep -q "Error"; then
    echo "Unmounting OverlayFS from $MERGED_DIR..."
    sudo umount "$MERGED_DIR"; fi
}

setup_overlayfs() {
  echo "Setting up OverlayFS..."
  sudo mount -t overlay overlay -o lowerdir="$MOUNT_POINT",upperdir="$UPPER_DIR",workdir="$WORK_DIR" "$MERGED_DIR"
}

# Display usage
usage() {
    echo "Usage: $0 {init|cleanup|status}"
    echo "  init    - Mount the NFS share and setup overlayFS."
    echo "  cleanup - Unmount the overlayFS and NFS share."
    echo "  status   - Check the status of the NFS and overlayfs mount."
}

setup_nfs_overlayfs() {
  create_workdirs

  # mount dune nfs cache
  [[ $(check_dune_nfs_status | grep -c "not mounted") -gt 0 ]] && mount_dune_nfs
  nfs_status=$(check_dune_nfs_status)
  echo "$nfs_status"
  [[ $(echo "$nfs_status" | grep -c "not mounted") -gt 0 ]] && exit 10

  # mount overlayfs
  [[ $(check_overlayfs_status | grep -c "not mounted") -gt 0 ]] && setup_overlayfs
  overlayfs_status=$(check_overlayfs_status)
  echo "$overlayfs_status"
  [[ $(echo "$overlayfs_status" | grep -c "not mounted") -gt 0 ]] && exit 10 || exit 0
}

cleanup_nfs_overlayfs() {
  [[ $(check_overlayfs_status | grep -c "is mounted") -gt 0 ]] && umount_overlayfs
  echo "Status: $(check_overlayfs_status)"
  [[ $(check_dune_nfs_status | grep -c "is mounted") -gt 0 ]] && umount_dune_nfs
  echo "Status: $(check_dune_nfs_status)"
}

# Main logic to process options
case "$1" in
    init)
	setup_nfs_overlayfs
        ;;
    cleanup)
	cleanup_nfs_overlayfs
        ;;
    status)
        check_dune_nfs_status
	check_overlayfs_status
        ;;
    *)
        usage
        exit 1
        ;;
esac

