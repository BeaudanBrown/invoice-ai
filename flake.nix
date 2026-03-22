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
        packages.default = pkgs.writeTextFile {
          name = "invoice-ai-foundation";
          destination = "/share/doc/invoice-ai/README";
          text = builtins.readFile ./README.md;
        };

        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            git
            just
            nil
            nixfmt
          ];
        };
      };

      flake = {
        nixosModules.invoice-ai = import ./modules/invoice-ai.nix;
        nixosModules.default = import ./modules/invoice-ai.nix;
      };
    };
}
