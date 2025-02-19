{
  perSystem =
    { pkgs, ... }:
    {
      devShells.default = pkgs.mkShell {
        packages = with pkgs; [
          git
          nix
          nixos-rebuild
          python3.pkgs.colorlog
          python3.pkgs.deploykit
          python3.pkgs.invoke
          python3.pkgs.tabulate
          sops
          ssh-to-age
        ];
      };
    };
}
