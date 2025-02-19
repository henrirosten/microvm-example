{
  self,
  inputs,
  lib,
  microvm,
  ...
}:
let
  specialArgs = {
    inherit self inputs;
  };
in
{
  flake.nixosModules = {
    hosts-common = import ./hosts-common.nix;
    nixos-builder = ./builder/conf.nix;
    nixos-jenkins-controller = ./jenkins-controller/conf.nix;
  };
  flake.nixosConfigurations = {

    # 'builder' with:
    # https://github.com/NixOS/nixpkgs/blob/master/nixos/modules/virtualisation/qemu-vm.nix
    builder-nixosvm = lib.nixosSystem {
      inherit specialArgs;
      modules = [
        (import ./nixos-qemu.nix { })
        self.nixosModules.nixos-builder
        {
          virtualisation.vmVariant.virtualisation.forwardPorts = [
            {
              from = "host";
              host.port = 2322;
              guest.port = 22;
            }
          ];
        }
      ];
    };

    # 'builder' with:
    # https://github.com/astro/microvm.nix
    builder-microvm = lib.nixosSystem {
      inherit specialArgs;
      modules = [
        self.nixosModules.nixos-builder
        microvm.nixosModules.microvm
        (import ./microvm-qemu.nix { name = "builder"; })
        {
          microvm.forwardPorts = [
            {
              from = "host";
              host.port = 2322;
              guest.port = 22;
            }
          ];
        }
      ];
    };

    # 'jenkins-controller' with:
    # https://github.com/NixOS/nixpkgs/blob/master/nixos/modules/virtualisation/qemu-vm.nix
    jenkins-nixosvm = lib.nixosSystem {
      inherit specialArgs;
      modules = [
        (import ./nixos-qemu.nix {
          ram_gb = 20;
          disk_gb = 150;
        })
        self.nixosModules.nixos-jenkins-controller
        {
          virtualisation.vmVariant.virtualisation.forwardPorts = [
            {
              from = "host";
              host.port = 8081;
              guest.port = 8081;
            }
            {
              from = "host";
              host.port = 2222;
              guest.port = 22;
            }
          ];
        }
      ];
    };

    # 'jenkins-controller' with:
    # https://github.com/astro/microvm.nix
    jenkins-microvm = lib.nixosSystem {
      inherit specialArgs;
      modules = [
        self.nixosModules.nixos-jenkins-controller
        microvm.nixosModules.microvm
        (import ./microvm-qemu.nix {
          name = "jenkins-controller";
          ram_gb = 20;
          disk_gb = 20;
        })
        {
          microvm.forwardPorts = [
            {
              from = "host";
              host.port = 8081;
              guest.port = 8081;
            }
            {
              from = "host";
              host.port = 2222;
              guest.port = 22;
            }
          ];
        }
      ];
    };
  };
  flake.packages."x86_64-linux" = {
    # https://github.com/astro/microvm.nix
    builder-microvm = self.nixosConfigurations.builder-microvm.config.microvm.declaredRunner;
    jenkins-microvm = self.nixosConfigurations.jenkins-microvm.config.microvm.declaredRunner;

    # https://github.com/NixOS/nixpkgs/blob/master/nixos/modules/virtualisation/qemu-vm.nix
    builder-nixosvm = self.nixosConfigurations.builder-nixosvm.config.system.build."vm";
    jenkins-nixosvm = self.nixosConfigurations.jenkins-nixosvm.config.system.build."vm";
  };
}
