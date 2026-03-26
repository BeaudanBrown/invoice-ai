{ lib, pkgs, config, ... }:
let
  cfg = config.services.invoice-ai;
  defaultPython = pkgs.python3.withPackages (ps: with ps; [
    fastapi
    pydantic
    uvicorn
  ]);
  defaultPackage = pkgs.writeShellApplication {
    name = "invoice-ai";
    runtimeInputs = [ defaultPython ];
    text = ''
      export PYTHONPATH="${../src}:''${PYTHONPATH:-}"
      exec ${defaultPython}/bin/python3 ${../bin/invoice-ai} "$@"
    '';
  };
  runtimeEnvironment = lib.filterAttrs (_: value: value != null) {
    INVOICE_AI_LISTEN_ADDRESS = cfg.listenAddress;
    INVOICE_AI_PORT = toString cfg.port;
    INVOICE_AI_PUBLIC_URL = cfg.publicUrl;
    INVOICE_AI_HOST_NAME = cfg.hostName;
    INVOICE_AI_OPERATOR_TOKENS_FILE =
      if cfg.operatorAuth.tokensFile != null
      then toString cfg.operatorAuth.tokensFile
      else null;
    INVOICE_AI_STATE_DIR = cfg.stateDir;
    INVOICE_AI_DOCUMENTS_DIR = cfg.documentsDir;
    INVOICE_AI_MEMORY_DIR = cfg.memoryDir;
    INVOICE_AI_INGEST_DIR = cfg.ingestDir;
    INVOICE_AI_APPROVALS_DIR = cfg.approvalsDir;
    INVOICE_AI_REVISIONS_DIR = cfg.revisionsDir;
    INVOICE_AI_ARTIFACTS_DIR = cfg.artifactsDir;
    INVOICE_AI_CACHE_DIR = cfg.cacheDir;
    INVOICE_AI_ERPNEXT_URL = cfg.erpnext.url;
    INVOICE_AI_ERPNEXT_CREDENTIALS_FILE =
      if cfg.erpnext.credentialsFile != null
      then toString cfg.erpnext.credentialsFile
      else null;
    INVOICE_AI_OLLAMA_URL = cfg.ollama.url;
    INVOICE_AI_DOCLING_URL = cfg.docling.url;
    INVOICE_AI_N8N_URL = cfg.n8n.url;
  };
in
{
  options.services.invoice-ai = {
    enable = lib.mkEnableOption "invoice-ai foundation service";

    package = lib.mkOption {
      type = lib.types.package;
      default = defaultPackage;
      description = "invoice-ai application package used by the service.";
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

    operatorAuth = {
      tokensFile = lib.mkOption {
        type = lib.types.nullOr lib.types.path;
        default = null;
        description = "Host-provided JSON file containing bearer tokens mapped to operator ids for the FastAPI operator surface.";
      };
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

    systemd.services.invoice-ai = {
      description = "invoice-ai control-plane service";
      wantedBy = [ "multi-user.target" ];
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      environment = runtimeEnvironment;
      serviceConfig = {
        Type = "simple";
        User = cfg.user;
        Group = cfg.group;
        WorkingDirectory = cfg.stateDir;
        ExecStartPre = "${cfg.package}/bin/invoice-ai init-paths";
        ExecStart = "${cfg.package}/bin/invoice-ai serve-http";
        Restart = "on-failure";
        RestartSec = 5;
      };
      serviceConfig.EnvironmentFile =
        lib.optional (cfg.environmentFile != null) cfg.environmentFile;
    };
  };
}
