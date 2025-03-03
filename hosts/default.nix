{
  inputs,
  self,
  ...
}:
let
  specialArgs = {
    inherit inputs self;
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
    builder-nixosvm = inputs.nixpkgs.lib.nixosSystem {
      inherit specialArgs;
      modules = [
        (import ./vm-nixos-qemu.nix {
          inherit (self.nixosConfigurations.builder-nixosvm) config;
        })
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
    builder-microvm = inputs.nixpkgs.lib.nixosSystem {
      inherit specialArgs;
      modules = [
        self.nixosModules.nixos-builder
        inputs.microvm.nixosModules.microvm
        (import ./vm-microvm-qemu.nix {
          inherit inputs;
          inherit (self.nixosConfigurations.builder-nixosvm) config;
        })
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
    jenkins-nixosvm = inputs.nixpkgs.lib.nixosSystem {
      inherit specialArgs;
      modules = [
        (import ./vm-nixos-qemu.nix {
          inherit (self.nixosConfigurations.jenkins-nixosvm) config;
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
    jenkins-microvm = inputs.nixpkgs.lib.nixosSystem {
      inherit specialArgs;
      modules = [
        self.nixosModules.nixos-jenkins-controller
        inputs.microvm.nixosModules.microvm
        (import ./vm-microvm-qemu.nix {
          inherit inputs;
          inherit (self.nixosConfigurations.jenkins-nixosvm) config;
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
}
