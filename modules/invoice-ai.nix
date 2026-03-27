{ lib, pkgs, config, ... }:
let
  cfg = config.services.invoice-ai;
  erpCfg = cfg.erpnext;
  erpEnabled = cfg.enable && erpCfg.mode == "embedded";
  erpNetwork = "invoice-ai-erpnext";
  erpRuntimeUid = 1000;
  erpRuntimeGid = 1000;
  mariadbRuntimeUid = 999;
  mariadbRuntimeGid = 999;
  erpImage = "${erpCfg.image}:${erpCfg.version}";
  mariadbImage = "${erpCfg.database.image}:${erpCfg.database.version}";
  redisImage = "${erpCfg.redis.image}:${erpCfg.redis.version}";
  erpFrontendUrl = "http://127.0.0.1:${toString erpCfg.frontendPort}";
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
    INVOICE_AI_ERPNEXT_URL =
      if erpEnabled
      then erpFrontendUrl
      else cfg.erpnext.url;
    INVOICE_AI_ERPNEXT_CREDENTIALS_FILE =
      if cfg.erpnext.credentialsFile != null
      then toString cfg.erpnext.credentialsFile
      else null;
    INVOICE_AI_OLLAMA_URL = cfg.ollama.url;
    INVOICE_AI_DOCLING_URL = cfg.docling.url;
    INVOICE_AI_N8N_URL = cfg.n8n.url;
  };
  erpContainerVolumes = [
    "${erpCfg.volumes.sitesDir}:/home/frappe/frappe-bench/sites"
    "${erpCfg.volumes.logsDir}:/home/frappe/frappe-bench/logs"
  ];
  erpBootstrapServiceNames = [
    "invoice-ai-erpnext-network.service"
    "invoice-ai-erpnext-secrets.service"
    "invoice-ai-erpnext-configure.service"
    "invoice-ai-erpnext-create-site.service"
    "invoice-ai-erpnext-apply-site-config.service"
  ];
  erpBackendServiceUnits = [
    "podman-erpnext-backend.service"
    "podman-erpnext-frontend.service"
    "podman-erpnext-websocket.service"
    "podman-erpnext-queue-short.service"
    "podman-erpnext-queue-long.service"
    "podman-erpnext-scheduler.service"
  ];
  erpBackendServiceAttrs = [
    "podman-erpnext-backend"
    "podman-erpnext-frontend"
    "podman-erpnext-websocket"
    "podman-erpnext-queue-short"
    "podman-erpnext-queue-long"
    "podman-erpnext-scheduler"
  ];
  erpConfigureScript = pkgs.writeShellApplication {
    name = "invoice-ai-erpnext-configure";
    runtimeInputs = [ config.virtualisation.podman.package ];
    text = ''
      set -euo pipefail

      exec podman run --rm \
        --network ${erpNetwork} \
        -v ${erpCfg.volumes.sitesDir}:/home/frappe/frappe-bench/sites \
        -v ${erpCfg.volumes.logsDir}:/home/frappe/frappe-bench/logs \
        -e DB_HOST=db \
        -e DB_PORT=${toString erpCfg.database.port} \
        -e REDIS_CACHE=redis-cache:${toString erpCfg.redis.cachePort} \
        -e REDIS_QUEUE=redis-queue:${toString erpCfg.redis.queuePort} \
        -e SOCKETIO_PORT=9000 \
        ${erpImage} \
        bash -lc '
          set -euo pipefail
          ls -1 apps > sites/apps.txt
          bench set-config -g db_host "$DB_HOST"
          bench set-config -gp db_port "$DB_PORT"
          bench set-config -g redis_cache "redis://$REDIS_CACHE"
          bench set-config -g redis_queue "redis://$REDIS_QUEUE"
          bench set-config -g redis_socketio "redis://$REDIS_QUEUE"
          bench set-config -gp socketio_port "$SOCKETIO_PORT"
          bench set-config -g chromium_path /usr/bin/chromium-headless-shell
        '
    '';
  };
  erpCreateSiteScript = pkgs.writeShellApplication {
    name = "invoice-ai-erpnext-create-site";
    runtimeInputs = [ config.virtualisation.podman.package ];
    text = ''
      set -euo pipefail

      bootstrap_marker="${erpCfg.volumes.sitesDir}/${erpCfg.siteName}/.invoice-ai-bootstrap-complete"
      if [ -f "$bootstrap_marker" ]; then
        exit 0
      fi

      db_root_password="$(tr -d '\n' < ${toString erpCfg.secrets.dbRootPasswordFile})"
      db_password="$(tr -d '\n' < ${toString erpCfg.secrets.dbPasswordFile})"
      admin_password="$(tr -d '\n' < ${toString erpCfg.secrets.adminPasswordFile})"

      exec podman run --rm \
        --network ${erpNetwork} \
        -v ${erpCfg.volumes.sitesDir}:/home/frappe/frappe-bench/sites \
        -v ${erpCfg.volumes.logsDir}:/home/frappe/frappe-bench/logs \
        -e SITE_NAME=${lib.escapeShellArg erpCfg.siteName} \
        -e SITE_DB_NAME=${lib.escapeShellArg erpCfg.database.name} \
        -e SITE_DB_USER=${lib.escapeShellArg erpCfg.database.user} \
        -e SITE_DB_PASSWORD="$db_password" \
        -e DB_ROOT_PASSWORD="$db_root_password" \
        -e ADMIN_PASSWORD="$admin_password" \
        ${erpImage} \
        bash -lc '
          set -euo pipefail

          wait_for_port() {
            local host="$1"
            local port="$2"
            local label="$3"
            for _ in $(seq 1 120); do
              if (echo >"/dev/tcp/$host/$port") >/dev/null 2>&1; then
                return 0
              fi
              sleep 1
            done
            echo "Timed out waiting for $label at $host:$port" >&2
            exit 1
          }

          wait_for_port db ${toString erpCfg.database.port} database
          wait_for_port redis-cache ${toString erpCfg.redis.cachePort} redis-cache
          wait_for_port redis-queue ${toString erpCfg.redis.queuePort} redis-queue

          start=$(date +%s)
          until [ -n "$(grep -hs ^ sites/common_site_config.json | jq -r ".db_host // empty")" ] \
            && [ -n "$(grep -hs ^ sites/common_site_config.json | jq -r ".redis_cache // empty")" ] \
            && [ -n "$(grep -hs ^ sites/common_site_config.json | jq -r ".redis_queue // empty")" ]; do
            sleep 2
            if [ $(( $(date +%s) - start )) -gt 120 ]; then
              echo "common_site_config.json is missing required connection keys" >&2
              exit 1
            fi
          done

          bench new-site \
            --mariadb-user-host-login-scope=% \
            --db-root-username=root \
            --db-root-password="$DB_ROOT_PASSWORD" \
            --db-name="$SITE_DB_NAME" \
            --db-user="$SITE_DB_USER" \
            --db-password="$SITE_DB_PASSWORD" \
            --admin-password="$ADMIN_PASSWORD" \
            --install-app erpnext \
            --set-default \
            "$SITE_NAME"

          touch "sites/$SITE_NAME/.invoice-ai-bootstrap-complete"
        '
    '';
  };
  erpApplySiteConfigScript = pkgs.writeShellApplication {
    name = "invoice-ai-erpnext-apply-site-config";
    runtimeInputs = [ config.virtualisation.podman.package ];
    text = ''
      set -euo pipefail

      site_config="${erpCfg.volumes.sitesDir}/${erpCfg.siteName}/site_config.json"
      if [ ! -f "$site_config" ]; then
        echo "ERPNext site ${erpCfg.siteName} has not been created yet" >&2
        exit 1
      fi

      encryption_key="$(tr -d '\n' < ${toString erpCfg.secrets.frappeSecretKeyFile})"

      exec podman run --rm \
        --network ${erpNetwork} \
        -v ${erpCfg.volumes.sitesDir}:/home/frappe/frappe-bench/sites \
        -v ${erpCfg.volumes.logsDir}:/home/frappe/frappe-bench/logs \
        -e SITE_NAME=${lib.escapeShellArg erpCfg.siteName} \
        -e ENCRYPTION_KEY="$encryption_key" \
        -e SITE_PUBLIC_URL=${lib.escapeShellArg (erpCfg.publicUrl or "")} \
        ${erpImage} \
        bash -lc '
          set -euo pipefail
          bench --site "$SITE_NAME" set-config encryption_key "$ENCRYPTION_KEY"
          if [ -n "$SITE_PUBLIC_URL" ]; then
            bench --site "$SITE_NAME" set-config host_name "$SITE_PUBLIC_URL"
          fi
        '
    '';
  };
  mkErpServiceWiring =
    names:
    lib.genAttrs names (_: {
      after = erpBootstrapServiceNames;
      requires = erpBootstrapServiceNames;
    });
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
      description = "Listen address for the invoice-ai control-plane service.";
    };

    port = lib.mkOption {
      type = lib.types.port;
      default = 4310;
      description = "Listen port for the invoice-ai control-plane service.";
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
      mode = lib.mkOption {
        type = lib.types.enum [
          "external"
          "embedded"
        ];
        default = "external";
        description = "Whether invoice-ai connects to an external ERPNext instance or deploys one through OCI containers.";
      };

      url = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        description = "Base URL for the external ERPNext instance used by invoice-ai.";
      };

      publicUrl = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        description = "Optional externally reachable URL for the embedded ERPNext frontend.";
      };

      credentialsFile = lib.mkOption {
        type = lib.types.nullOr lib.types.path;
        default = null;
        description = "Optional host-provided file containing ERPNext API credentials for invoice-ai.";
      };

      siteName = lib.mkOption {
        type = lib.types.str;
        default = "erpnext.local";
        description = "Bench site name to create when ERPNext runs in embedded mode.";
      };

      siteHost = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        description = "Optional host header that the ERPNext frontend should route to the embedded site.";
      };

      image = lib.mkOption {
        type = lib.types.str;
        default = "frappe/erpnext";
        description = "OCI image repository used for ERPNext/Frappe application containers.";
      };

      version = lib.mkOption {
        type = lib.types.str;
        default = "v16.11.0";
        description = "ERPNext image tag used for the embedded deployment.";
      };

      backendPort = lib.mkOption {
        type = lib.types.port;
        default = 18000;
        description = "Host-local debug port published for the embedded ERPNext backend.";
      };

      frontendPort = lib.mkOption {
        type = lib.types.port;
        default = 18080;
        description = "Host-local port published for the embedded ERPNext frontend.";
      };

      websocketPort = lib.mkOption {
        type = lib.types.port;
        default = 19000;
        description = "Host-local debug port published for the embedded ERPNext websocket service.";
      };

      database = {
        image = lib.mkOption {
          type = lib.types.str;
          default = "mariadb";
          description = "OCI image repository used for the embedded MariaDB container.";
        };

        version = lib.mkOption {
          type = lib.types.str;
          default = "10.6";
          description = "MariaDB image tag used for the embedded deployment.";
        };

        host = lib.mkOption {
          type = lib.types.str;
          default = "db";
          description = "Internal hostname used by ERPNext to reach MariaDB inside the container network.";
        };

        port = lib.mkOption {
          type = lib.types.port;
          default = 3306;
          description = "Internal MariaDB port used inside the ERPNext container network.";
        };

        name = lib.mkOption {
          type = lib.types.str;
          default = "invoice_ai_erpnext";
          description = "Database name to create for the default ERPNext site.";
        };

        user = lib.mkOption {
          type = lib.types.str;
          default = "invoice_ai_erpnext";
          description = "Database user to create for the default ERPNext site.";
        };

        dataDir = lib.mkOption {
          type = lib.types.str;
          default = "/var/lib/invoice-ai/erpnext/db";
          description = "Persistent MariaDB data directory for the embedded ERPNext deployment.";
        };
      };

      redis = {
        image = lib.mkOption {
          type = lib.types.str;
          default = "redis";
          description = "OCI image repository used for the embedded Redis containers.";
        };

        version = lib.mkOption {
          type = lib.types.str;
          default = "6.2-alpine";
          description = "Redis image tag used for the embedded deployment.";
        };

        cachePort = lib.mkOption {
          type = lib.types.port;
          default = 6379;
          description = "Internal port used by the embedded Redis cache container.";
        };

        queuePort = lib.mkOption {
          type = lib.types.port;
          default = 6379;
          description = "Internal port used by the embedded Redis queue container.";
        };

        cacheDataDir = lib.mkOption {
          type = lib.types.str;
          default = "/var/lib/invoice-ai/erpnext/redis-cache";
          description = "Persistent data directory for the embedded Redis cache container.";
        };

        queueDataDir = lib.mkOption {
          type = lib.types.str;
          default = "/var/lib/invoice-ai/erpnext/redis-queue";
          description = "Persistent data directory for the embedded Redis queue container.";
        };
      };

      volumes = {
        stateDir = lib.mkOption {
          type = lib.types.str;
          default = "/var/lib/invoice-ai/erpnext";
          description = "Persistent state root for the embedded ERPNext deployment.";
        };

        sitesDir = lib.mkOption {
          type = lib.types.str;
          default = "/var/lib/invoice-ai/erpnext/sites";
          description = "Persistent sites directory for the embedded ERPNext deployment.";
        };

        logsDir = lib.mkOption {
          type = lib.types.str;
          default = "/var/lib/invoice-ai/erpnext/logs";
          description = "Persistent logs directory for the embedded ERPNext deployment.";
        };
      };

      secrets = {
        dbRootPasswordFile = lib.mkOption {
          type = lib.types.nullOr lib.types.path;
          default = null;
          description = "Host-provided file containing the embedded MariaDB root password.";
        };

        dbPasswordFile = lib.mkOption {
          type = lib.types.nullOr lib.types.path;
          default = null;
          description = "Host-provided file containing the ERPNext site database password.";
        };

        adminPasswordFile = lib.mkOption {
          type = lib.types.nullOr lib.types.path;
          default = null;
          description = "Host-provided file containing the initial ERPNext Administrator password.";
        };

        frappeSecretKeyFile = lib.mkOption {
          type = lib.types.nullOr lib.types.path;
          default = null;
          description = "Host-provided file containing the persistent ERPNext site encryption key.";
        };
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

  config = lib.mkIf cfg.enable (lib.mkMerge [
    {
      assertions = [
        {
          assertion = cfg.operatorAuth.tokensFile != null;
          message = "services.invoice-ai.operatorAuth.tokensFile must be set.";
        }
        {
          assertion = erpCfg.mode != "external" || erpCfg.url != null;
          message = "services.invoice-ai.erpnext.url must be set when services.invoice-ai.erpnext.mode = \"external\".";
        }
        {
          assertion =
            erpCfg.mode != "embedded"
            || (
              erpCfg.secrets.dbRootPasswordFile != null
              && erpCfg.secrets.dbPasswordFile != null
              && erpCfg.secrets.adminPasswordFile != null
              && erpCfg.secrets.frappeSecretKeyFile != null
            );
          message = "Embedded ERPNext mode requires dbRootPasswordFile, dbPasswordFile, adminPasswordFile, and frappeSecretKeyFile.";
        }
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

      systemd.services.invoice-ai = {
        description = "invoice-ai control-plane service";
        wantedBy = [ "multi-user.target" ];
        after =
          [
            "network-online.target"
            "invoice-ai-prepare-paths.service"
          ]
          ++ lib.optionals erpEnabled [
            "invoice-ai-erpnext-apply-site-config.service"
            "podman-erpnext-frontend.service"
          ];
        wants =
          [
            "network-online.target"
            "invoice-ai-prepare-paths.service"
          ]
          ++ lib.optionals erpEnabled [
            "invoice-ai-erpnext-apply-site-config.service"
            "podman-erpnext-frontend.service"
          ];
        requires = [ "invoice-ai-prepare-paths.service" ];
        environment = runtimeEnvironment;
        serviceConfig = {
          Type = "simple";
          User = cfg.user;
          Group = cfg.group;
          WorkingDirectory = cfg.stateDir;
          ExecStartPre = "${cfg.package}/bin/invoice-ai init-paths";
          ExecStart = "${cfg.package}/bin/invoice-ai serve-http";
          ReadWritePaths = [
            cfg.stateDir
            cfg.documentsDir
            cfg.memoryDir
            cfg.ingestDir
            cfg.approvalsDir
            cfg.revisionsDir
            cfg.artifactsDir
            cfg.cacheDir
          ];
          Restart = "on-failure";
          RestartSec = 5;
        };
        serviceConfig.EnvironmentFile =
          lib.optional (cfg.environmentFile != null) cfg.environmentFile;
      };

      systemd.services.invoice-ai-prepare-paths = {
        description = "invoice-ai runtime path preparation";
        wantedBy = [ "multi-user.target" ];
        before = [ "invoice-ai.service" ];
        path = [ pkgs.coreutils ];
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
        };
        script = ''
          set -euo pipefail

          install -d -m 0750 -o ${cfg.user} -g ${cfg.group} ${cfg.stateDir}
          install -d -m 0750 -o ${cfg.user} -g ${cfg.group} ${cfg.documentsDir}
          install -d -m 0750 -o ${cfg.user} -g ${cfg.group} ${cfg.memoryDir}
          install -d -m 0750 -o ${cfg.user} -g ${cfg.group} ${cfg.ingestDir}
          install -d -m 0750 -o ${cfg.user} -g ${cfg.group} ${cfg.approvalsDir}
          install -d -m 0750 -o ${cfg.user} -g ${cfg.group} ${cfg.revisionsDir}
          install -d -m 0750 -o ${cfg.user} -g ${cfg.group} ${cfg.artifactsDir}
          install -d -m 0750 -o ${cfg.user} -g ${cfg.group} ${cfg.cacheDir}
        '';
      };
    }

    (lib.mkIf erpEnabled {
      virtualisation.podman.enable = true;

      systemd.tmpfiles.rules = [
        "d ${erpCfg.volumes.stateDir} 0750 root root - -"
        "d ${erpCfg.volumes.sitesDir} 0770 ${toString erpRuntimeUid} ${toString erpRuntimeGid} - -"
        "d ${erpCfg.volumes.logsDir} 0770 ${toString erpRuntimeUid} ${toString erpRuntimeGid} - -"
        "d ${erpCfg.database.dataDir} 0700 ${toString mariadbRuntimeUid} ${toString mariadbRuntimeGid} - -"
        "d ${erpCfg.redis.cacheDataDir} 0700 root root - -"
        "d ${erpCfg.redis.queueDataDir} 0700 root root - -"
      ];

      virtualisation.oci-containers.containers = {
        erpnext-db = {
          image = mariadbImage;
          environmentFiles = [ "/run/invoice-ai-erpnext/mariadb.env" ];
          cmd = [
            "--character-set-server=utf8mb4"
            "--collation-server=utf8mb4_unicode_ci"
            "--skip-character-set-client-handshake"
            "--skip-innodb-read-only-compressed"
          ];
          volumes = [ "${erpCfg.database.dataDir}:/var/lib/mysql" ];
          networks = [ erpNetwork ];
          extraOptions = [ "--network-alias=db" ];
        };

        erpnext-redis-cache = {
          image = redisImage;
          volumes = [ "${erpCfg.redis.cacheDataDir}:/data" ];
          networks = [ erpNetwork ];
          extraOptions = [ "--network-alias=redis-cache" ];
        };

        erpnext-redis-queue = {
          image = redisImage;
          volumes = [ "${erpCfg.redis.queueDataDir}:/data" ];
          networks = [ erpNetwork ];
          extraOptions = [ "--network-alias=redis-queue" ];
        };

        erpnext-backend = {
          image = erpImage;
          ports = [ "127.0.0.1:${toString erpCfg.backendPort}:8000" ];
          volumes = erpContainerVolumes;
          networks = [ erpNetwork ];
          dependsOn = [
            "erpnext-db"
            "erpnext-redis-cache"
            "erpnext-redis-queue"
          ];
          extraOptions = [ "--network-alias=backend" ];
        };

        erpnext-frontend = {
          image = erpImage;
          cmd = [ "nginx-entrypoint.sh" ];
          ports = [ "127.0.0.1:${toString erpCfg.frontendPort}:8080" ];
          volumes = erpContainerVolumes;
          networks = [ erpNetwork ];
          dependsOn = [
            "erpnext-backend"
            "erpnext-websocket"
          ];
          environment = {
            BACKEND = "backend:8000";
            SOCKETIO = "websocket:9000";
            FRAPPE_SITE_NAME_HEADER =
              if erpCfg.siteHost != null
              then erpCfg.siteHost
              else "$host";
            UPSTREAM_REAL_IP_ADDRESS = "127.0.0.1";
            UPSTREAM_REAL_IP_HEADER = "X-Forwarded-For";
            UPSTREAM_REAL_IP_RECURSIVE = "off";
            PROXY_READ_TIMEOUT = "120";
            CLIENT_MAX_BODY_SIZE = "50m";
          };
          extraOptions = [ "--network-alias=frontend" ];
        };

        erpnext-websocket = {
          image = erpImage;
          cmd = [
            "node"
            "/home/frappe/frappe-bench/apps/frappe/socketio.js"
          ];
          ports = [ "127.0.0.1:${toString erpCfg.websocketPort}:9000" ];
          volumes = erpContainerVolumes;
          networks = [ erpNetwork ];
          dependsOn = [
            "erpnext-db"
            "erpnext-redis-cache"
            "erpnext-redis-queue"
          ];
          environment = {
            FRAPPE_REDIS_CACHE = "redis://redis-cache:${toString erpCfg.redis.cachePort}";
            FRAPPE_REDIS_QUEUE = "redis://redis-queue:${toString erpCfg.redis.queuePort}";
          };
          extraOptions = [ "--network-alias=websocket" ];
        };

        erpnext-queue-short = {
          image = erpImage;
          cmd = [ "bench" "worker" "--queue" "short,default" ];
          volumes = erpContainerVolumes;
          networks = [ erpNetwork ];
          dependsOn = [
            "erpnext-db"
            "erpnext-redis-cache"
            "erpnext-redis-queue"
          ];
          environment = {
            FRAPPE_REDIS_CACHE = "redis://redis-cache:${toString erpCfg.redis.cachePort}";
            FRAPPE_REDIS_QUEUE = "redis://redis-queue:${toString erpCfg.redis.queuePort}";
          };
        };

        erpnext-queue-long = {
          image = erpImage;
          cmd = [ "bench" "worker" "--queue" "long,default,short" ];
          volumes = erpContainerVolumes;
          networks = [ erpNetwork ];
          dependsOn = [
            "erpnext-db"
            "erpnext-redis-cache"
            "erpnext-redis-queue"
          ];
          environment = {
            FRAPPE_REDIS_CACHE = "redis://redis-cache:${toString erpCfg.redis.cachePort}";
            FRAPPE_REDIS_QUEUE = "redis://redis-queue:${toString erpCfg.redis.queuePort}";
          };
        };

        erpnext-scheduler = {
          image = erpImage;
          cmd = [ "bench" "schedule" ];
          volumes = erpContainerVolumes;
          networks = [ erpNetwork ];
          dependsOn = [
            "erpnext-db"
            "erpnext-redis-cache"
            "erpnext-redis-queue"
          ];
        };
      };

      systemd.services = {
        invoice-ai-erpnext-network = {
          description = "invoice-ai ERPNext podman network";
          wantedBy = [ "multi-user.target" ];
          before = [
            "invoice-ai-erpnext-secrets.service"
            "invoice-ai-erpnext-configure.service"
            "invoice-ai-erpnext-create-site.service"
            "invoice-ai-erpnext-apply-site-config.service"
          ] ++ erpBackendServiceUnits;
          after = [ "podman.service" ];
          requires = [ "podman.service" ];
          path = [
            config.virtualisation.podman.package
            pkgs.coreutils
          ];
          serviceConfig = {
            Type = "oneshot";
            RemainAfterExit = true;
          };
          script = ''
            set -euo pipefail
            install -d -m 0750 -o root -g root ${erpCfg.volumes.stateDir}
            install -d -m 0770 -o ${toString erpRuntimeUid} -g ${toString erpRuntimeGid} ${erpCfg.volumes.sitesDir}
            install -d -m 0770 -o ${toString erpRuntimeUid} -g ${toString erpRuntimeGid} ${erpCfg.volumes.logsDir}
            install -d -m 0700 -o ${toString mariadbRuntimeUid} -g ${toString mariadbRuntimeGid} ${erpCfg.database.dataDir}
            install -d -m 0700 -o root -g root ${erpCfg.redis.cacheDataDir}
            install -d -m 0700 -o root -g root ${erpCfg.redis.queueDataDir}
            if [ ! -f ${erpCfg.volumes.sitesDir}/common_site_config.json ]; then
              printf '{}\n' > ${erpCfg.volumes.sitesDir}/common_site_config.json
            fi
            chown ${toString erpRuntimeUid}:${toString erpRuntimeGid} ${erpCfg.volumes.sitesDir}/common_site_config.json
            chmod 0660 ${erpCfg.volumes.sitesDir}/common_site_config.json
            podman network exists ${erpNetwork} || podman network create ${erpNetwork}
          '';
        };

        invoice-ai-erpnext-secrets = {
          description = "invoice-ai ERPNext runtime secret preparation";
          wantedBy = [ "multi-user.target" ];
          before = [
            "invoice-ai-erpnext-configure.service"
            "invoice-ai-erpnext-create-site.service"
            "invoice-ai-erpnext-apply-site-config.service"
          ] ++ erpBackendServiceUnits;
          after = [ "invoice-ai-erpnext-network.service" ];
          requires = [ "invoice-ai-erpnext-network.service" ];
          serviceConfig = {
            Type = "oneshot";
            RemainAfterExit = true;
            RuntimeDirectory = "invoice-ai-erpnext";
          };
          script = ''
            set -euo pipefail

            db_root_password="$(tr -d '\n' < ${toString erpCfg.secrets.dbRootPasswordFile})"

            cat > /run/invoice-ai-erpnext/mariadb.env <<EOF
            MYSQL_ROOT_PASSWORD=$db_root_password
            MARIADB_ROOT_PASSWORD=$db_root_password
            EOF

            chmod 0400 /run/invoice-ai-erpnext/mariadb.env
          '';
        };

        invoice-ai-erpnext-configure = {
          description = "invoice-ai ERPNext bench configuration";
          wantedBy = [ "multi-user.target" ];
          before = [
            "invoice-ai-erpnext-create-site.service"
          ] ++ erpBackendServiceUnits;
          after = [
            "invoice-ai-erpnext-secrets.service"
            "podman-erpnext-db.service"
            "podman-erpnext-redis-cache.service"
            "podman-erpnext-redis-queue.service"
          ];
          requires = [
            "invoice-ai-erpnext-secrets.service"
            "podman-erpnext-db.service"
            "podman-erpnext-redis-cache.service"
            "podman-erpnext-redis-queue.service"
          ];
          serviceConfig = {
            Type = "oneshot";
            RemainAfterExit = true;
          };
          script = "${erpConfigureScript}/bin/invoice-ai-erpnext-configure";
        };

        invoice-ai-erpnext-create-site = {
          description = "invoice-ai ERPNext site bootstrap";
          wantedBy = [ "multi-user.target" ];
          before = [
            "invoice-ai-erpnext-apply-site-config.service"
          ] ++ erpBackendServiceUnits;
          after = [
            "invoice-ai-erpnext-configure.service"
            "podman-erpnext-db.service"
            "podman-erpnext-redis-cache.service"
            "podman-erpnext-redis-queue.service"
          ];
          requires = [
            "invoice-ai-erpnext-configure.service"
            "podman-erpnext-db.service"
            "podman-erpnext-redis-cache.service"
            "podman-erpnext-redis-queue.service"
          ];
          serviceConfig = {
            Type = "oneshot";
            RemainAfterExit = true;
          };
          script = "${erpCreateSiteScript}/bin/invoice-ai-erpnext-create-site";
        };

        invoice-ai-erpnext-apply-site-config = {
          description = "invoice-ai ERPNext stable site configuration";
          wantedBy = [ "multi-user.target" ];
          before = erpBackendServiceUnits ++ [ "invoice-ai.service" ];
          after = [ "invoice-ai-erpnext-create-site.service" ];
          requires = [ "invoice-ai-erpnext-create-site.service" ];
          serviceConfig = {
            Type = "oneshot";
            RemainAfterExit = true;
          };
          script = "${erpApplySiteConfigScript}/bin/invoice-ai-erpnext-apply-site-config";
        };
      } // mkErpServiceWiring erpBackendServiceAttrs;
    })
  ]);
}
