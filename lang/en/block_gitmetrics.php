<?php
// ── Cadenas de idioma (Inglés) para block_gitmetrics ─────────────────────

// Plugin
$string['pluginname']                  = 'Git Knowledge Base Metrics';
$string['gitmetrics:addinstance']      = 'Add a Git KB Metrics block';
$string['gitmetrics:myaddinstance']    = 'Add a Git KB Metrics block to My Moodle';
$string['gitmetrics:viewmetrics']      = 'View Git KB Metrics';

// Settings (global)
$string['github_token']                = 'GitHub API Token';
$string['github_token_desc']           = 'Optional Personal Access Token (classic or fine-grained). Without a token, the GitHub API allows 60 requests/hour per IP. With a token, the limit rises to 5,000/hour. Required for private repositories.';
$string['cache_ttl']                   = 'Cache TTL (seconds)';
$string['cache_ttl_desc']              = 'How long (in seconds) the calculated metrics are cached in the database before being recalculated. Default: 3600 (1 hour).';
$string['default_branch']             = 'Default branch';
$string['default_branch_desc']        = 'Default Git branch to analyse if none is specified per block instance (e.g. main or master).';

// Edit form (per-instance)
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
$string['no_repo_configured']          = 'No repository URL configured. Edit this block and paste a GitHub repository URL.';
$string['last_updated']                = 'Last updated';
$string['view_repo']                   = 'View repository';
$string['refresh_metrics']             = 'Refresh metrics';
$string['files_detail']                = 'File details';
$string['bytes']                       = 'bytes';
$string['words']                       = 'words';
$string['present']                     = 'Present';
$string['missing']                     = 'Missing';

// Errors
$string['error_invalid_url']           = 'Invalid GitHub URL. Expected format: https://github.com/owner/repo';
$string['error_api']                   = 'Could not connect to the GitHub API. Check that the repository is public or that a valid token is configured.';
$string['error_json']                  = 'Unexpected response from the GitHub API (JSON parse error).';
$string['error_repo']                  = 'Repository not found or inaccessible';
$string['error_branch']                = 'Branch not found. Try changing the branch in the block settings.';
