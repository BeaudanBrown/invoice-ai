{ lib, pkgs, config, ... }:
let
  cfg = config.services.invoice-ai;
in
{
  options.services.invoice-ai = {
    enable = lib.mkEnableOption "invoice-ai foundation service";

    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.writeTextFile {
        name = "invoice-ai-foundation";
        destination = "/share/doc/invoice-ai/README";
        text = "invoice-ai foundation package placeholder\n";
      };
      description = "Placeholder package for the future invoice-ai application bundle.";
    };

    stateDir = lib.mkOption {
      type = lib.types.str;
      default = "/var/lib/invoice-ai";
      description = "Persistent state directory for invoice-ai owned files.";
    };

    documentsDir = lib.mkOption {
      type = lib.types.str;
      default = "/var/lib/invoice-ai/documents";
      description = "Persistent document store for ingested invoices and receipts.";
    };

    hostName = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "Optional external hostname used by the deployed service.";
    };
  };

  config = lib.mkIf cfg.enable {
    warnings = [
      "services.invoice-ai is currently a foundation-stage module placeholder; application services are not wired yet."
    ];

    systemd.tmpfiles.rules = [
      "d ${cfg.stateDir} 0750 root root - -"
      "d ${cfg.documentsDir} 0750 root root - -"
    ];
  };
}
