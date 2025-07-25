import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

const FeatureList = [
  {
    title: '🔌 Easy Integration',
    Svg: require('@site/static/img/undraw_docusaurus_mountain.svg').default,
    description: (
      <>
        IoWarp MCPs integrate seamlessly with Claude Code, Claude Desktop, VS Code, 
        and Cursor. Get started with scientific computing AI tools in minutes.
      </>
    ),
  },
  {
    title: '🧪 Scientific Focus',
    Svg: require('@site/static/img/undraw_docusaurus_tree.svg').default,
    description: (
      <>
        Built specifically for research and scientific computing workflows. 
        Access data processing, analysis, and system management capabilities 
        tailored for science.
      </>
    ),
  },
  {
    title: '⚡ High Performance',
    Svg: require('@site/static/img/undraw_docusaurus_react.svg').default,
    description: (
      <>
        Optimized for large-scale data processing and analysis. Handle scientific 
        datasets, simulations, and computational workflows with efficiency.
      </>
    ),
  },
];

function Feature({Svg, title, description}) {
  return (
    <div className={clsx('col col--4')}>
      <div className="text--center">
        <Svg className={styles.featureSvg} role="img" />
      </div>
      <div className="text--center padding-horiz--md">
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures() {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
