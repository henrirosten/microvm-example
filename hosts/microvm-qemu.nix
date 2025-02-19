{
  name,
  vcpus ? 4,
  ram_gb ? 16,
  disk_gb ? 16,
}:
let
  hash = str: builtins.hashString "sha256" str;
  oct = off: str: builtins.substring off 2 (hash str);
  str2mac = s: "02:${oct 2 s}:${oct 4 s}:${oct 6 s}:${oct 8 s}:${oct 10 s}";
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
        mac = builtins.trace "Using 'vm-qemu-${name}' mac: ${str2mac name}" (str2mac name);
      }
    ];
    writableStoreOverlay = "/nix/.rw-store";
    volumes = [
      {
        mountPoint = "/";
        image = "microvm.${toString name}.persist.img";
        size = disk_gb * 1024;
      }
    ];
  };
}
