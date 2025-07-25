import React, { useState, useMemo } from 'react';
import Link from '@docusaurus/Link';
import { mcpData, categories, popularMcps } from '../../data/mcpData';
import styles from './styles.module.css';

// Platform icons component
const PlatformIcons = ({ platforms }) => {
  const platformIcons = {
    claude: '🤖',
    cursor: '⚡',
    vscode: '💻'
  };

  return (
    <div className={styles.platformIcons}>
      {platforms.map((platform) => (
        <span key={platform} className={styles.platformIcon} title={platform}>
          {platformIcons[platform]}
        </span>
      ))}
    </div>
  );
};

// Individual MCP card component
const MCPCard = ({ mcpId, mcp }) => {
  return (
    <Link to={`/docs/mcps/${mcp.slug}`} className={styles.mcpCard}>
      <div className={styles.mcpCardHeader}>
        <div className={styles.mcpIcon}>{mcp.icon}</div>
        <div className={styles.mcpCardInfo}>
          <h3 className={styles.mcpName}>{mcp.name}</h3>
          <span className={styles.mcpCategory}>{mcp.category}</span>
        </div>
        <PlatformIcons platforms={mcp.platforms} />
      </div>
      <p className={styles.mcpDescription}>{mcp.description}</p>
      <div className={styles.mcpStats}>
        <span className={styles.mcpVersion}>v{mcp.stats.version}</span>
        <span className={styles.mcpActions}>{mcp.actions.length} actions</span>
      </div>
    </Link>
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
          <span className={styles.categoryIcon}>{data.icon}</span>
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
        <span className={styles.searchIcon}>🔍</span>
        <input
          type="text"
          placeholder="Search MCPs, categories, and capabilities..."
          value={searchTerm}
          onChange={(e) => onSearchChange(e.target.value)}
          className={styles.searchInput}
        />
      </div>
    </div>
  );
};

// Main showcase component
const MCPShowcase = () => {
  const [activeCategory, setActiveCategory] = useState('All');
  const [searchTerm, setSearchTerm] = useState('');

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
        mcp.actions.some(action => action.toLowerCase().includes(term))
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
      <div className={styles.showcaseHeader}>
        <h1 className={styles.showcaseTitle}>
          🔬 IOWarp MCPs
        </h1>
        <p className={styles.showcaseSubtitle}>
          AI Tools for Scientific Computing - Discover powerful Model Context Protocol servers
        </p>
        
        <SearchBar 
          searchTerm={searchTerm} 
          onSearchChange={setSearchTerm} 
        />
        
        <CategoryFilter 
          activeCategory={activeCategory}
          onCategoryChange={setActiveCategory}
        />
      </div>


      {/* All MCPs section */}
      <section className={styles.allMcpsSection}>
        <h2 className={styles.sectionTitle}>
          {searchTerm ? `Search Results (${filteredMcps.length})` : 
           activeCategory === 'All' ? 'All MCPs' : activeCategory}
        </h2>
        
        {filteredMcps.length === 0 ? (
          <div className={styles.noResults}>
            <p>No MCPs found matching your criteria.</p>
            <button 
              onClick={() => {
                setSearchTerm('');
                setActiveCategory('All');
              }}
              className={styles.clearFilters}
            >
              Clear Filters
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