import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import MCPShowcase from '@site/src/components/MCPShowcase';

export default function Home() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout
      title={`${siteConfig.title}`}
      description="AI Tools for Scientific Computing - Model Context Protocol servers for data processing, analysis, and system management">
      <main>
        <MCPShowcase />
      </main>
    </Layout>
  );
}
