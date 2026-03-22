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

    memoryDir = lib.mkOption {
      type = lib.types.str;
      default = "/var/lib/invoice-ai/memory";
      description = "Persistent markdown memory directory for operator, client, and job guidance.";
    };

    ingestDir = lib.mkOption {
      type = lib.types.str;
      default = "/var/lib/invoice-ai/ingest";
      description = "Persistent ingest work directory for source material and extraction proposals.";
    };

    approvalsDir = lib.mkOption {
      type = lib.types.str;
      default = "/var/lib/invoice-ai/approvals";
      description = "Persistent approval artifact directory.";
    };

    revisionsDir = lib.mkOption {
      type = lib.types.str;
      default = "/var/lib/invoice-ai/revisions";
      description = "Persistent working revision snapshot directory for draft quote and invoice iterations.";
    };

    artifactsDir = lib.mkOption {
      type = lib.types.str;
      default = "/var/lib/invoice-ai/artifacts";
      description = "Persistent generated artifact directory for PDFs and structured review outputs.";
    };

    cacheDir = lib.mkOption {
      type = lib.types.str;
      default = "/var/lib/invoice-ai/cache";
      description = "Rebuildable cache directory for temporary extraction or inference outputs.";
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
      "d ${cfg.memoryDir} 0750 root root - -"
      "d ${cfg.ingestDir} 0750 root root - -"
      "d ${cfg.approvalsDir} 0750 root root - -"
      "d ${cfg.revisionsDir} 0750 root root - -"
      "d ${cfg.artifactsDir} 0750 root root - -"
      "d ${cfg.cacheDir} 0750 root root - -"
    ];
  };
}
