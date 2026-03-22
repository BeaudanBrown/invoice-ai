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

    user = lib.mkOption {
      type = lib.types.str;
      default = "invoice-ai";
      description = "Runtime user for the invoice-ai service.";
    };

    group = lib.mkOption {
      type = lib.types.str;
      default = "invoice-ai";
      description = "Runtime group for the invoice-ai service.";
    };

    listenAddress = lib.mkOption {
      type = lib.types.str;
      default = "127.0.0.1";
      description = "Listen address for the future invoice-ai control-plane service.";
    };

    port = lib.mkOption {
      type = lib.types.port;
      default = 4310;
      description = "Listen port for the future invoice-ai control-plane service.";
    };

    publicUrl = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "Optional externally reachable base URL exposed by the host.";
    };

    environmentFile = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = "Host-provided environment file containing runtime secrets and service credentials.";
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

    erpnext = {
      url = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        description = "Base URL for the ERPNext instance used by invoice-ai.";
      };

      credentialsFile = lib.mkOption {
        type = lib.types.nullOr lib.types.path;
        default = null;
        description = "Optional host-provided file containing ERPNext API credentials.";
      };
    };

    ollama = {
      url = lib.mkOption {
        type = lib.types.str;
        default = "http://127.0.0.1:11434";
        description = "Base URL for the Ollama instance used for local inference.";
      };
    };

    docling = {
      url = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        description = "Optional base URL for a Docling service endpoint.";
      };
    };

    n8n = {
      url = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        description = "Optional base URL for an n8n instance used by future orchestration flows.";
      };
    };
  };

  config = lib.mkIf cfg.enable {
    warnings = [
      "services.invoice-ai currently defines the service boundary, runtime options, and persistence contract; the application systemd service is not wired yet."
    ];

    users.groups.${cfg.group} = {};

    users.users.${cfg.user} = {
      isSystemUser = true;
      group = cfg.group;
      home = cfg.stateDir;
      createHome = false;
    };

    systemd.tmpfiles.rules = [
      "d ${cfg.stateDir} 0750 ${cfg.user} ${cfg.group} - -"
      "d ${cfg.documentsDir} 0750 ${cfg.user} ${cfg.group} - -"
      "d ${cfg.memoryDir} 0750 ${cfg.user} ${cfg.group} - -"
      "d ${cfg.ingestDir} 0750 ${cfg.user} ${cfg.group} - -"
      "d ${cfg.approvalsDir} 0750 ${cfg.user} ${cfg.group} - -"
      "d ${cfg.revisionsDir} 0750 ${cfg.user} ${cfg.group} - -"
      "d ${cfg.artifactsDir} 0750 ${cfg.user} ${cfg.group} - -"
      "d ${cfg.cacheDir} 0750 ${cfg.user} ${cfg.group} - -"
    ];
  };
}
