import React, { useState, useMemo } from 'react';
import Link from '@docusaurus/Link';
import { mcpData, categories, popularMcps, githubStats, categoryTypes, mcpEndorsement } from '../../data/mcpData';
import styles from './styles.module.css';

const getDocPath = (mcp) => mcp.docPath || `/docs/mcps/${mcp.slug}`;

// Toast Notification Component
const Toast = ({ message, show, onClose }) => {
  React.useEffect(() => {
    if (show) {
      const timer = setTimeout(onClose, 2500);
      return () => clearTimeout(timer);
    }
  }, [show, onClose]);

  if (!show) return null;

  return (
    <div className={styles.toast}>
      <div className={styles.toastContent}>
        <span className={styles.toastIcon}>✓</span>
        <span className={styles.toastMessage}>{message}</span>
      </div>
    </div>
  );
};

// Platform Button Component with Copy Functionality
const PlatformButton = ({ platform, mcpName, onCopy }) => {
  const platformConfig = {
    claude: { label: 'Claude', logo: 'claude-logo.png' },
    cursor: { label: 'Cursor', logo: 'cursor-logo.png' },
    vscode: { label: 'VSCode', logo: 'vscode-logo.png' },
    gemini: { label: 'Gemini', logo: 'gemini-logo.png' }
  };

  const config = platformConfig[platform];
  const installCommand = `uvx clio-kit ${mcpName.toLowerCase().replace(/ /g, '-')}`;

  const handleClick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    navigator.clipboard.writeText(installCommand);
    onCopy(`${config.label} install copied!`);
  };

  return (
    <button
      className={styles.platformButton}
      onClick={handleClick}
      title={`Copy install command for ${config.label}`}
    >
      <img
        src={`/img/logos/${config.logo}`}
        alt={config.label}
        className={styles.platformIcon}
      />
      <span className={styles.platformName}>{config.label}</span>
    </button>
  );
};

// Featured MCP Card Component - Completely different structure
const FeaturedMCPCard = ({ mcpId, mcp, onCopy }) => {
  const stats = githubStats[mcpId] || {};
  const categoryTag = categoryTypes[mcp.category] || 'OTHER';
  const toolCount = mcp.actions.length;
  const endorsement = mcpEndorsement[mcpId] || 'COMMUNITY';

  // Determine special tag
  const getSpecialTag = () => {
    if (mcpId === 'ndp') return { label: 'NEW', type: 'new' };
    return { label: 'POPULAR', type: 'popular' };
  };

  const specialTag = getSpecialTag();

  return (
    <Link to={getDocPath(mcp)} className={styles.featuredCard} data-category={mcp.category}>
      {/* Top Tags Row - 4 tags now */}
      <div className={styles.featuredTags}>
        <span className={`${styles.featuredTag} ${styles.tagEndorsement}`}>
          {endorsement}
        </span>
        <span className={`${styles.featuredTag} ${styles.tagType}`}>{categoryTag}</span>
        <span className={`${styles.featuredTag} ${styles.tagTools}`}>{toolCount} TOOLS</span>
        <span className={`${styles.featuredTag} ${styles[`tag${specialTag.type.charAt(0).toUpperCase() + specialTag.type.slice(1)}`]}`}>
          {specialTag.label}
        </span>
      </div>

      {/* Title Section with Logo */}
      <div className={styles.featuredHeader}>
        <img
          src={`/img/logos/${mcpId}-logo.svg`}
          alt={`${mcp.name} logo`}
          className={styles.featuredLogo}
          onError={(e) => {
            // Try PNG if SVG fails
            const pngSrc = `/img/logos/${mcpId}-logo.png`;
            if (!e.target.src.endsWith('.png')) {
              e.target.src = pngSrc;
            } else {
              // Both failed, hide logo
              e.target.style.display = 'none';
            }
          }}
        />
        <div className={styles.featuredTitleSection}>
          <h3 className={styles.featuredName}>{mcp.name}</h3>
          <div className={styles.featuredMeta}>
            <span className={styles.featuredVersion}>v{mcp.stats.version}</span>
            <span className={styles.metaSeparator}>·</span>
            <a
              href={`https://github.com/iowarp/clio-kit/tree/main/clio-kit-mcp-servers/${mcpId}`}
              className={styles.githubLinkInline}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
            >
              <svg className={styles.githubIconInline} viewBox="0 0 16 16" fill="currentColor">
                <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
              </svg>
              Star on Github
            </a>
          </div>
        </div>
      </div>

      {/* Description */}
      <p className={styles.featuredDescription}>{mcp.description}</p>

      {/* Divider */}
      <div className={styles.featuredDivider}></div>

      {/* Platform Section - Simple text hint */}
      <div className={styles.platformSection}>
        <p className={styles.platformHint}>
          Try it out now in your favorite Agent
        </p>
        <div className={styles.platformGrid} onClick={(e) => e.preventDefault()}>
          <PlatformButton platform="claude" mcpName={mcp.name} onCopy={onCopy} />
          <PlatformButton platform="cursor" mcpName={mcp.name} onCopy={onCopy} />
          <PlatformButton platform="vscode" mcpName={mcp.name} onCopy={onCopy} />
          <PlatformButton platform="gemini" mcpName={mcp.name} onCopy={onCopy} />
        </div>
      </div>
    </Link>
  );
};

// Platform icons component (for regular cards)
const PlatformIcons = ({ platforms }) => {
  const platformLabels = {
    claude: 'Claude',
    cursor: 'Cursor',
    vscode: 'VSCode'
  };

  return (
    <div className={styles.platformIcons}>
      {platforms.map((platform) => (
        <span key={platform} className={styles.platformLabel} title={platform}>
          {platformLabels[platform] || platform}
        </span>
      ))}
    </div>
  );
};

// Badge component for special labels
const Badge = ({ type, label }) => {
  const badgeClass = {
    new: styles.badgeNew,
    tools: styles.badgeTools,
  }[type] || '';

  return (
    <span className={`${styles.badge} ${badgeClass}`}>
      {label}
    </span>
  );
};

// Individual MCP card component (regular cards, not featured) - SIMPLIFIED
const MCPCard = ({ mcpId, mcp }) => {
  const categoryTag = categoryTypes[mcp.category] || 'OTHER';

  return (
    <div className={styles.mcpCard} data-category={mcp.category}>
      <div className={styles.mcpCardHeader}>
        <div className={styles.mcpIcon}>{mcp.icon}</div>
        <span className={styles.mcpCategoryTag}>{categoryTag}</span>
      </div>

      <h3 className={styles.mcpName}>{mcp.name}</h3>
      <p className={styles.mcpDescription}>{mcp.description}</p>

      <Link to={getDocPath(mcp)} className={styles.mcpButton}>
        View Details
      </Link>
    </div>
  );
};

// Category filter component
const CategoryFilter = ({ activeCategory, onCategoryChange }) => {
  return (
    <div className={styles.categoryFilter}>
      {Object.entries(categories).map(([category, data]) => (
        <button
          key={category}
          className={`${styles.categoryButton} ${
            activeCategory === category ? styles.active : ''
          }`}
          onClick={() => onCategoryChange(category)}
          style={{
            '--category-color': data.color
          }}
        >
          <span className={styles.categoryName}>{category}</span>
          <span className={styles.categoryCount}>{data.count}</span>
        </button>
      ))}
    </div>
  );
};

// Search component
const SearchBar = ({ searchTerm, onSearchChange }) => {
  return (
    <div className={styles.searchContainer}>
      <div className={styles.searchBox}>
        <span className={styles.searchIcon} aria-hidden="true" />
        <input
          type="text"
          placeholder="Search by name, category, or tool... (try: hdf5, slurm, pandas)"
          value={searchTerm}
          onChange={(e) => onSearchChange(e.target.value)}
          className={styles.searchInput}
          aria-label="Search MCP servers"
        />
      </div>
    </div>
  );
};

// Main showcase component
const MCPShowcase = () => {
  const [activeCategory, setActiveCategory] = useState('All');
  const [searchTerm, setSearchTerm] = useState('');
  const [toast, setToast] = useState({ show: false, message: '' });

  const showToast = (message) => {
    setToast({ show: true, message });
  };

  const hideToast = () => {
    setToast({ show: false, message: '' });
  };

  // Filter MCPs based on category and search
  const filteredMcps = useMemo(() => {
    let filtered = Object.entries(mcpData);

    // Filter by category
    if (activeCategory !== 'All') {
      filtered = filtered.filter(([_, mcp]) => mcp.category === activeCategory);
    }

    // Filter by search term
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(([_, mcp]) =>
        mcp.name.toLowerCase().includes(term) ||
        mcp.description.toLowerCase().includes(term) ||
        mcp.category.toLowerCase().includes(term) ||
        (mcp.actions && mcp.actions.some(action => action.toLowerCase().includes(term)))
      );
    }

    return filtered;
  }, [activeCategory, searchTerm]);

  // Get popular MCPs for featured section
  const featuredMcps = useMemo(() => {
    return popularMcps.map(id => [id, mcpData[id]]).filter(([_, mcp]) => mcp);
  }, []);

  return (
    <div className={styles.showcase}>
      {/* Toast Notification */}
      <Toast message={toast.message} show={toast.show} onClose={hideToast} />

      {/* FEATURED MCPs - First */}
      {featuredMcps.length > 0 && !searchTerm && activeCategory === 'All' && (
        <section className={styles.featuredSection} aria-label="Featured MCPs">
          <h2 className={styles.featuredTitle}>Featured MCPs</h2>
          <div className={styles.featuredGrid}>
            {featuredMcps.map(([mcpId, mcp]) => (
              <FeaturedMCPCard key={`featured-${mcpId}`} mcpId={mcpId} mcp={mcp} onCopy={showToast} />
            ))}
          </div>
        </section>
      )}

      {/* Section Header with Inline Highlights */}
      <div className={styles.showcaseHeader}>
        <h2 className={styles.showcaseTitle}>Browse All Servers</h2>
        <p className={styles.showcaseHighlight}>
          Formats • Analytics • HPC • Performance • Research • Utilities
        </p>
      </div>

      {/* Floating Search */}
      <SearchBar
        searchTerm={searchTerm}
        onSearchChange={setSearchTerm}
      />

      {/* Floating Category Chips */}
      <CategoryFilter
        activeCategory={activeCategory}
        onCategoryChange={setActiveCategory}
      />

      {/* All MCPs Grid */}
      <section className={styles.allMcpsSection}>
        <h2 className={styles.sectionTitle}>
          {searchTerm ? `${filteredMcps.length} Matches` : `${activeCategory} (${filteredMcps.length})`}
        </h2>

        {filteredMcps.length === 0 ? (
          <div className={styles.noResults}>
            <p>No servers found. Try different filters.</p>
            <button
              onClick={() => {
                setSearchTerm('');
                setActiveCategory('All');
              }}
              className={styles.clearFilters}
            >
              Reset Filters
            </button>
          </div>
        ) : (
          <div className={styles.mcpGrid}>
            {filteredMcps.map(([mcpId, mcp]) => (
              <MCPCard key={mcpId} mcpId={mcpId} mcp={mcp} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
};

export default MCPShowcase;
