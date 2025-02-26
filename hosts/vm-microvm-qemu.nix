{
  config,
  vcpus ? 4,
  ram_gb ? 16,
  disk_gb ? 16,
  ...
}:
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
    volumes = [
      {
        mountPoint = "/";
        image = "microvm.${config.system.name}.persist.img";
        size = disk_gb * 1024;
      }
    ];
  };
}
