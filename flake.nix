{
  description = "Nix-native self-hosted AI invoicing workspace";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
  };

  outputs = inputs@{ flake-parts, nixpkgs, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];

      perSystem = { pkgs, ... }: {
        packages.default = pkgs.writeShellApplication {
          name = "invoice-ai";
          runtimeInputs = [ pkgs.python3 ];
          text = ''
            export PYTHONPATH="${./src}:''${PYTHONPATH:-}"
            exec python3 ${./bin/invoice-ai} "$@"
          '';
        };

        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            git
            just
            nil
            nixfmt
            python3
          ];
        };
      };

      flake = {
        nixosModules.invoice-ai = import ./modules/invoice-ai.nix;
        nixosModules.default = import ./modules/invoice-ai.nix;
      };
    };
}
