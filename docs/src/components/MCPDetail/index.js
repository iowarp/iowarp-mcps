import React, { useState } from 'react';
import Link from '@docusaurus/Link';
import CodeBlock from '@theme/CodeBlock';
import MDXContent from '@theme/MDXContent';
import styles from './styles.module.css';

const MCPDetail = ({ 
  name, 
  icon, 
  category, 
  description, 
  version, 
  actions, 
  platforms,
  keywords,
  license,
  tools = [],
  children 
}) => {
  const [activeTab, setActiveTab] = useState('installation');
  const [activeInstallTab, setActiveInstallTab] = useState('cursor');
  const [expandedAction, setExpandedAction] = useState(null);

  const installationConfigs = {
    cursor: {
      title: 'Cursor',
      language: 'json',
      code: `{
  "mcpServers": {
    "${name.toLowerCase()}-mcp": {
      "command": "uvx",
      "args": ["iowarp-mcps", "${name.toLowerCase()}"]
    }
  }
}`
    },
    vscode: {
      title: 'VS Code',
      language: 'json',
      code: `"mcp": {
  "servers": {
    "${name.toLowerCase()}-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["iowarp-mcps", "${name.toLowerCase()}"]
    }
  }
}`
    },
    claude_code: {
      title: 'Claude Code',
      language: 'bash',
      code: `claude mcp add ${name.toLowerCase()}-mcp -- uvx iowarp-mcps ${name.toLowerCase()}`
    },
    claude_desktop: {
      title: 'Claude Desktop',
      language: 'json',
      code: `{
  "mcpServers": {
    "${name.toLowerCase()}-mcp": {
      "command": "uvx",
      "args": ["iowarp-mcps", "${name.toLowerCase()}"]
    }
  }
}`
    },
    manual: {
      title: 'Manual Setup',
      language: 'bash',
      code: `# Linux/macOS
CLONE_DIR=$(pwd)
git clone https://github.com/iowarp/iowarp-mcps.git
uv --directory=$CLONE_DIR/iowarp-mcps/mcps/${name} run ${name.toLowerCase()}-mcp --help

# Windows CMD
set CLONE_DIR=%cd%
git clone https://github.com/iowarp/iowarp-mcps.git
uv --directory=%CLONE_DIR%\\iowarp-mcps\\mcps\\${name} run ${name.toLowerCase()}-mcp --help

# Windows PowerShell
$env:CLONE_DIR=$PWD
git clone https://github.com/iowarp/iowarp-mcps.git
uv --directory=$env:CLONE_DIR\\iowarp-mcps\\mcps\\${name} run ${name.toLowerCase()}-mcp --help`
    }
  };

  const getPlatformIcon = (platform) => {
    const icons = {
      claude: '🤖',
      cursor: '⚡',
      vscode: '💻'
    };
    return icons[platform] || '🔧';
  };

  // Parse examples from children content and structure them like actions
  const parseExamples = (children) => {
    if (!children || typeof children !== 'object') return [];
    
    // Convert React elements to text for parsing
    let content = '';
    if (React.isValidElement(children)) {
      // Try to extract text content from React elements
      const extractText = (element) => {
        if (typeof element === 'string') return element;
        if (typeof element === 'number') return String(element);
        if (React.isValidElement(element) && element.props.children) {
          if (Array.isArray(element.props.children)) {
            return element.props.children.map(extractText).join('');
          }
          return extractText(element.props.children);
        }
        return '';
      };
      content = extractText(children);
    } else if (Array.isArray(children)) {
      content = children.map(child => {
        if (typeof child === 'string') return child;
        if (React.isValidElement(child)) {
          const extractText = (element) => {
            if (typeof element === 'string') return element;
            if (typeof element === 'number') return String(element);
            if (React.isValidElement(element) && element.props.children) {
              if (Array.isArray(element.props.children)) {
                return element.props.children.map(extractText).join('');
              }
              return extractText(element.props.children);
            }
            return '';
          };
          return extractText(child);
        }
        return String(child);
      }).join('');
    } else if (typeof children === 'string') {
      content = children;
    }
    
    // Parse examples from the content
    const examples = [];
    const sections = content.split(/###\s+\d+\.\s+/);
    
    sections.forEach((section, index) => {
      if (index === 0 || !section.trim()) return; // Skip empty first section
      
      const lines = section.trim().split('\n');
      const title = lines[0] || `Example ${index}`;
      
      // Extract code block
      let codeBlock = '';
      let description = '';
      let inCodeBlock = false;
      let afterCodeBlock = false;
      
      for (let i = 1; i < lines.length; i++) {
        const line = lines[i];
        if (line.startsWith('```') && !inCodeBlock) {
          inCodeBlock = true;
          continue;
        }
        if (line.startsWith('```') && inCodeBlock) {
          inCodeBlock = false;
          afterCodeBlock = true;
          continue;
        }
        if (inCodeBlock) {
          codeBlock += line + '\n';
        } else if (afterCodeBlock && line.trim()) {
          description += line + '\n';
        }
      }
      
      examples.push({
        id: `example-${index}`,
        title: title.trim(),
        code: codeBlock.trim(),
        description: description.trim()
      });
    });
    
    return examples;
  };

  // For now, we'll render all children content in the examples tab
  // The markdown is now structured to only contain examples
  const renderContent = (children) => {
    // Check if children is a React element/component already processed by MDX
    if (React.isValidElement(children)) {
      return children;
    }
    
    // If it's an array of elements, render each one
    if (Array.isArray(children)) {
      return children.map((child, index) => (
        React.isValidElement(child) ? (
          <div key={index}>{child}</div>
        ) : (
          <div key={index}>{String(child)}</div>
        )
      ));
    }
    
    // If it's a string, wrap it in a div
    if (typeof children === 'string') {
      return <div>{children}</div>;
    }
    
    // Default case
    return children;
  };

  // Simple markdown-like renderer for tool descriptions
  const renderMarkdownDescription = (text) => {
    if (!text) return <p>No description available.</p>;
    
    // Split by bullet points and render as list
    const lines = text.split('\n').filter(line => line.trim());
    const hasBullets = lines.some(line => line.trim().startsWith('-') || line.trim().startsWith('*'));
    
    if (hasBullets) {
      const listItems = lines
        .filter(line => line.trim().startsWith('-') || line.trim().startsWith('*'))
        .map((line, index) => (
          <li key={index}>{line.replace(/^[\s\-\*]+/, '').trim()}</li>
        ));
      
      const nonListContent = lines
        .filter(line => !(line.trim().startsWith('-') || line.trim().startsWith('*')))
        .join(' ');
      
      return (
        <div>
          {nonListContent && <p>{nonListContent}</p>}
          {listItems.length > 0 && <ul>{listItems}</ul>}
        </div>
      );
    }
    
    return <p>{text}</p>;
  };

  const toggleAction = (actionName) => {
    setExpandedAction(expandedAction === actionName ? null : actionName);
  };

  return (
    <div className={styles.mcpDetail}>
      {/* Header */}
      <div className={styles.header}>
        <Link to="/" className={styles.backButton}>
          ← Back to MCPs
        </Link>
        
        <div className={styles.mcpInfo}>
          <div className={styles.mcpHeader}>
            <div className={styles.mcpIcon}>{icon}</div>
            <div className={styles.mcpTitleSection}>
              <h1 className={styles.mcpTitle}>{name}</h1>
              <div className={styles.mcpMeta}>
                <span className={styles.mcpCategory}>{category}</span>
                <span className={styles.mcpVersion}>v{version}</span>
                <div className={styles.platformSupport}>
                  {platforms.map(platform => (
                    <span key={platform} className={styles.platformIcon} title={platform}>
                      {getPlatformIcon(platform)}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
          <p className={styles.mcpDescription}>{description}</p>
          
          {/* Project Information */}
          {(keywords || license) && (
            <div className={styles.projectInfo}>
              {keywords && keywords.length > 0 && (
                <div className={styles.projectInfoItem}>
                  <strong>Keywords:</strong> {keywords.slice(0, 8).join(', ')}
                </div>
              )}
              {license && (
                <div className={styles.projectInfoItem}>
                  <strong>License:</strong> {license}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Tab Navigation */}
      <div className={styles.tabNavigation}>
        <button 
          className={`${styles.mainTab} ${activeTab === 'installation' ? styles.active : ''}`}
          onClick={() => setActiveTab('installation')}
        >
          📥 Installation
        </button>
        <button 
          className={`${styles.mainTab} ${activeTab === 'actions' ? styles.active : ''}`}
          onClick={() => setActiveTab('actions')}
        >
          🔧 Actions ({actions?.length || 0})
        </button>
        <button 
          className={`${styles.mainTab} ${activeTab === 'examples' ? styles.active : ''}`}
          onClick={() => setActiveTab('examples')}
        >
          📝 Examples
        </button>
      </div>

      {/* Tab Content */}
      <div className={styles.tabContent}>
        {activeTab === 'installation' && (
          <div className={styles.installationTab}>
            <h2 id="installation">Installation</h2>
            <div className={styles.quickInstall}>
              <div className={styles.installTabs}>
                {Object.entries(installationConfigs).map(([key, config]) => (
                  <button
                    key={key}
                    className={`${styles.installTab} ${activeInstallTab === key ? styles.active : ''}`}
                    onClick={() => setActiveInstallTab(key)}
                  >
                    {config.title}
                  </button>
                ))}
              </div>
              <div className={styles.installContent}>
                <CodeBlock language={installationConfigs[activeInstallTab].language}>
                  {installationConfigs[activeInstallTab].code}
                </CodeBlock>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'actions' && (
          <div className={styles.actionsTab}>
            <h2 id="actions">Actions</h2>
            {tools && tools.length > 0 ? (
              <div className={styles.actionsGrid}>
                {tools.map((tool, index) => (
                  <div key={index} className={`${styles.actionCard} ${expandedAction === tool.name ? styles.expanded : ''}`} onClick={() => toggleAction(tool.name)}>
                    <div className={styles.actionHeader}>
                      <code className={styles.actionName}>{tool.name}</code>
                      <span className={styles.actionToggle}>
                        {expandedAction === tool.name ? '▼' : '▶'}
                      </span>
                    </div>
                    {expandedAction === tool.name && (
                      <div className={styles.actionDescription}>
                        {renderMarkdownDescription(tool.description)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : actions && actions.length > 0 && (
              <div className={styles.actionsGrid}>
                {actions.map((action, index) => (
                  <div key={index} className={`${styles.actionCard} ${expandedAction === action ? styles.expanded : ''}`} onClick={() => toggleAction(action)}>
                    <div className={styles.actionHeader}>
                      <code className={styles.actionName}>{action}</code>
                      <span className={styles.actionToggle}>
                        {expandedAction === action ? '▼' : '▶'}
                      </span>
                    </div>
                    {expandedAction === action && (
                      <div className={styles.actionDescription}>
                        <p>Tool functionality: {action.replace('_', ' ').toLowerCase()}</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'examples' && (
          <div className={styles.examplesTab}>
            <h2 id="examples">Examples</h2>
            {(() => {
              const examples = parseExamples(children);
              return examples.length > 0 ? (
                <div className={styles.examplesGrid}>
                  {examples.map((example, index) => (
                    <div key={index} className={`${styles.exampleCard} ${expandedAction === example.id ? styles.expanded : ''}`} onClick={() => toggleAction(example.id)}>
                      <div className={styles.actionHeader}>
                        <h4 className={styles.exampleTitle}>{example.title}</h4>
                        <span className={styles.actionToggle}>
                          {expandedAction === example.id ? '▼' : '▶'}
                        </span>
                      </div>
                      {expandedAction === example.id && (
                        <div className={styles.exampleExpansion}>
                          {example.code && (
                            <div className={styles.exampleCode}>
                              <h5>Prompt:</h5>
                              <CodeBlock language="text">
                                {example.code}
                              </CodeBlock>
                            </div>
                          )}
                          {example.description && (
                            <div className={styles.exampleDescription}>
                              <h5>Description:</h5>
                              {renderMarkdownDescription(example.description)}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className={styles.markdownContent}>
                  {renderContent(children)}
                </div>
              );
            })()}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className={styles.footer}>
        <div className={styles.footerLinks}>
          <Link href="https://github.com/iowarp/iowarp-mcps" className={styles.footerLink}>
            📖 View on GitHub
          </Link>
          <Link href="https://github.com/iowarp/iowarp-mcps/issues" className={styles.footerLink}>
            🐛 Report Issue
          </Link>
        </div>
        <p className={styles.footerText}>
          Part of the IOWarp MCPs collection - bringing AI practically to science!
        </p>
      </div>
    </div>
  );
};

export default MCPDetail;