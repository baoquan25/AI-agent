'use client';

type OutputPanelProps = {
  html: string;
  visible: boolean;
};

export function OutputPanel({ html, visible }: OutputPanelProps) {
  return (
    <div className={`panel-scroll output-panel ${visible ? '' : 'hidden'}`}>
      <div id="output" dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  );
}
