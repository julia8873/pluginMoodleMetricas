<?php
// ── Cadenas de idioma (Ingles) para block_gitmetrics ─────────────────────

// Plugin
$string['pluginname']                  = 'Git Knowledge Base Metrics';
$string['gitmetrics:addinstance']      = 'Add a Git KB Metrics block';
$string['gitmetrics:myaddinstance']    = 'Add a Git KB Metrics block to My Moodle';
$string['gitmetrics:viewmetrics']      = 'View Git KB Metrics';

// ── Settings - Proveedor ──────────────────────────────────────────────────
$string['default_provider']            = 'Default Git provider';
$string['default_provider_desc']       = 'Choose the Git provider used by default when creating a new block instance. Teachers can override this per block.';
$string['provider_github']             = 'GitHub (github.com)';
$string['provider_gitlab']             = 'GitLab (OSL / local / gitlab.com)';

// ── Settings - Secciones ──────────────────────────────────────────────────
$string['heading_github']              = 'GitHub settings';
$string['heading_gitlab']              = 'GitLab settings (OSL / local / cloud)';
$string['heading_general']             = 'General settings';

// Settings - GitHub
$string['github_token']                = 'GitHub API Token';
$string['github_token_desc']           = 'Optional Personal Access Token (classic or fine-grained). Without a token, the GitHub API allows 60 requests/hour per IP. With a token, the limit rises to 5,000/hour. Required for private repositories.';

// Settings - GitLab
$string['gitlab_url']                  = 'GitLab server URL';
$string['gitlab_url_desc']             = 'Base URL of the GitLab server to connect to. Examples: https://gitlab.com (cloud), https://gitlab.osl.ugr.es (OSL), http://localhost:8929 (local). Do not include a trailing slash.';
$string['gitlab_token']                = 'GitLab Access Token (PRIVATE-TOKEN)';
$string['gitlab_token_desc']           = 'Personal Access Token or Project Access Token for GitLab. Required for private repositories and for servers that require authentication. In GitLab go to User Settings > Access Tokens and create a token with read_api scope.';

// Settings - General
$string['cache_ttl']                   = 'Cache TTL (seconds)';
$string['cache_ttl_desc']              = 'How long (in seconds) the calculated metrics are cached in the database before being recalculated. Default: 3600 (1 hour).';
$string['default_branch']             = 'Default branch';
$string['default_branch_desc']        = 'Default Git branch to analyse if none is specified per block instance (e.g. main or master).';

// ── Edit form (per-instance) ──────────────────────────────────────────────
$string['provider']                    = 'Git provider';
$string['provider_help']               = 'Choose GitHub to connect to github.com, or GitLab to connect to a GitLab server (OSL, local, or gitlab.com). The server URL is configured globally by the site administrator in the plugin settings.';
$string['repo_url']                    = 'Repository URL';
$string['repo_url_help']               = "Paste the full URL of the repository to analyse.\n\nFor GitHub: https://github.com/owner/repo\nFor GitLab (OSL): https://gitlab.osl.ugr.es/group/repo\nFor local GitLab: http://localhost:8929/owner/repo";
// Backward compat
$string['github_url']                  = 'GitHub Repository URL';
$string['github_url_help']             = 'Paste the full public URL of the GitHub repository to analyse, e.g. https://github.com/user/repo';
$string['branch']                      = 'Branch';
$string['force_refresh']               = 'Force cache refresh';
$string['force_refresh_desc']          = 'Check this box to discard the cached results and recalculate all metrics on next load.';

// Section headings
$string['section_volume']              = 'Volume & Structure';
$string['section_network']             = 'Network & Connectivity';
$string['section_tags']                = 'Tag Metrics';
$string['section_format']              = 'Format Validation';

// Volume metrics labels
$string['metric_md_files']             = 'Markdown files';
$string['metric_total_files']          = 'Total files';
$string['metric_dirs']                 = 'Directories';
$string['metric_total_size']           = 'Total size';
$string['metric_avg_size']             = 'Avg. file size';
$string['metric_avg_words']            = 'Avg. word count';
$string['metric_max_words']            = 'Max. word count';
$string['metric_max_depth']            = 'Max. directory depth';
$string['metric_avg_depth']            = 'Avg. depth';
$string['essential_files']             = 'Essential files';

// Network metrics labels
$string['metric_total_nodes']          = 'Total nodes';
$string['metric_avg_connections']      = 'Avg. connections/node';
$string['metric_orphan_count']         = 'Orphan nodes';
$string['metric_orphan_rate']          = 'Orphan rate';
$string['metric_total_links']          = 'Total internal links';
$string['metric_link_density']         = 'Link density';
$string['link_density_desc']           = 'Internal links / total words';

// Tag metrics labels
$string['metric_unique_tags']          = 'Unique tags';
$string['metric_tag_usage']            = 'Total tag uses';
$string['metric_files_with_tags']      = 'Files with tags';
$string['metric_files_without_tags']   = 'Files without tags';
$string['metric_hamming_avg']          = 'Avg. Hamming distance';
$string['hamming_desc']                = 'Avg. pairwise Hamming distance between tag binary vectors (higher = more diverse tagging)';
$string['top_tags']                    = 'Top tags';

// Format metrics labels
$string['metric_frontmatter_rate']     = 'Frontmatter coverage';
$string['metric_valid_frontmatter']    = 'Valid frontmatter';
$string['metric_valid_markdown']       = 'Valid Markdown files';
$string['metric_valid_markdown_rate']  = 'Valid Markdown rate';
$string['frontmatter_errors']          = 'Frontmatter errors';

// Status / misc
$string['no_repo_configured']          = 'No repository URL configured. Edit this block, choose a Git provider (GitHub or GitLab) and paste the repository URL.';
$string['last_updated']                = 'Last updated';
$string['view_repo']                   = 'View repository';
$string['refresh_metrics']             = 'Refresh metrics';
$string['files_detail']                = 'File details';
$string['bytes']                       = 'bytes';
$string['words']                       = 'words';
$string['present']                     = 'Present';
$string['missing']                     = 'Missing';

// Errors
$string['error_invalid_url']           = 'Invalid repository URL. For GitHub use: https://github.com/owner/repo — For GitLab use: https://gitlab.example.com/group/repo';
$string['error_api']                   = 'Could not connect to the Git API. Check that the repository is accessible and that a valid token is configured (if the repository is private).';
$string['error_json']                  = 'Unexpected response from the API (JSON parse error).';
$string['error_repo']                  = 'Repository not found or inaccessible';
$string['error_branch']                = 'Branch not found. Try changing the branch in the block settings.';

// Obsidian (optional) — delete this block together with classes/obsidian_exporter.php and cli/export_obsidian.php
$string['heading_obsidian']            = 'Obsidian Integration (optional)';
$string['heading_obsidian_desc']       = 'Allows opening documents directly in Obsidian and exporting the knowledge base to a local vault. This feature is completely optional; you can ignore or disable it if not needed.';
$string['obsidian_enabled']            = 'Enable Obsidian integration';
$string['obsidian_enabled_desc']       = 'When enabled, a "🔮 Obsidian" button will appear next to each document that opens the note directly in the Obsidian desktop application.';
$string['obsidian_vault_path']         = 'Local Obsidian vault path';
$string['obsidian_vault_path_desc']    = 'Absolute path on the user\'s file system where the Obsidian vault is (or will be created). Example: /home/julia/Documents/OKF-Vault or C:\\Users\\julia\\Documents\\OKF-Vault';
$string['obsidian_vault_name']         = 'Obsidian vault name';
$string['obsidian_vault_name_desc']    = 'Exact name of the vault as Obsidian registered it when it was created (the vault folder name). This is used to build the obsidian:// protocol links.';
