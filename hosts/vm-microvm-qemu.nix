{
  config,
  inputs,
  vcpus ? 4,
  ram_gb ? 16,
  disk_gb ? 16,
  ...
}:
let
  pkgs = import inputs.nixpkgs { system = "x86_64-linux"; };
  create-cow2 = ''
    set -xeu
    name="./microvm.${config.system.name}.qcow2"
    size="${builtins.toString disk_gb}G"
    temp=$(mktemp)
    ${pkgs.qemu}/bin/qemu-img create -f raw "$temp" "$size"
    ${pkgs.e2fsprogs}/bin/mkfs.ext4 -L nixos "$temp"
    ${pkgs.qemu}/bin/qemu-img convert -f raw -O qcow2 "$temp" "$name"
    rm "$temp"
  '';
in
{
  microvm = {
    optimize.enable = false;
    hypervisor = "qemu";
    vcpu = vcpus;
    mem = ram_gb * 1024;
    interfaces = [
      {
        type = "user";
        id = "eth0";
        mac = "02:00:11:22:33:44";
      }
    ];
    writableStoreOverlay = "/nix/.rw-store";
    preStart = create-cow2;
    volumes = [
      {
        mountPoint = "/";
        autoCreate = false;
        image = "./microvm.${config.system.name}.qcow2";
      }
    ];
  };
}
