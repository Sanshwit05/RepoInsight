import React, { useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import { GraphData } from '../types';
import { Network, ZoomIn, ZoomOut, RotateCcw, Info } from 'lucide-react';

interface Props {
  graphData: GraphData;
  repoUrl: string;
}

export const DependencyGraphView: React.FC<Props> = ({ graphData, repoUrl }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [selectedNode, setSelectedNode] = useState<any | null>(null);

  useEffect(() => {
    if (!containerRef.current || !graphData.elements || graphData.total_nodes === 0) return;

    cyRef.current = cytoscape({
      container: containerRef.current,
      elements: graphData.elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#0969DA',
            'label': 'data(label)',
            'color': '#57606A',
            'font-size': '12px',
            'text-valign': 'bottom',
            'text-margin-y': 4,
            'width': 'mapData(in_degree, 0, 5, 20, 50)',
            'height': 'mapData(in_degree, 0, 5, 20, 50)',
            'border-width': 2,
            'border-color': '#54AEFF',
          },
        },
        {
          selector: 'node:selected',
          style: {
            'background-color': '#0969DA',
            'border-color': '#24292F',
            'border-width': 3,
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 1.5,
            'line-color': '#8C959F',
            'target-arrow-color': '#8C959F',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 0.8,
          },
        },
      ],
      layout: {
        name: 'cose',
        animate: false,
        padding: 30,
      } as any,
    });

    cyRef.current.on('tap', 'node', (evt) => {
      setSelectedNode(evt.target.data());
    });

    cyRef.current.on('tap', (evt) => {
      if (evt.target === cyRef.current) {
        setSelectedNode(null);
      }
    });

    return () => {
      cyRef.current?.destroy();
    };
  }, [graphData]);

  const handleZoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.25);
  const handleZoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() * 0.8);
  const handleReset = () => cyRef.current?.fit();

  return (
    <div className="bg-white border border-gh-border rounded-md p-4 space-y-3">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-gh-fg flex items-center gap-1.5">
            <Network className="w-4 h-4 text-gh-muted" strokeWidth={1.75} />
            Dependency Graph
          </h2>
          {repoUrl && (
            <p className="text-xs text-gh-muted mt-0.5">
              Repository: <span className="font-mono text-gh-fg">{repoUrl}</span>
            </p>
          )}
        </div>

        <div className="flex items-center space-x-2 text-xs">
          <span className="px-2 py-1 rounded-md bg-gh-canvas border border-gh-border text-gh-muted tabular-nums">
            {graphData.total_nodes} nodes
          </span>
          <span className="px-2 py-1 rounded-md bg-gh-canvas border border-gh-border text-gh-muted tabular-nums">
            {graphData.total_edges} edges
          </span>
          {graphData.total_nodes > 0 && (
            <div className="flex border border-gh-border rounded-md overflow-hidden">
              <button onClick={handleZoomIn} className="p-1.5 hover:bg-gh-canvas text-gh-muted border-r border-gh-border"><ZoomIn className="w-3.5 h-3.5" /></button>
              <button onClick={handleZoomOut} className="p-1.5 hover:bg-gh-canvas text-gh-muted border-r border-gh-border"><ZoomOut className="w-3.5 h-3.5" /></button>
              <button onClick={handleReset} className="p-1.5 hover:bg-gh-canvas text-gh-muted"><RotateCcw className="w-3.5 h-3.5" /></button>
            </div>
          )}
        </div>
      </div>

      {graphData.total_nodes === 0 ? (
        <div className="bg-gh-canvas border border-gh-border rounded-md p-8 text-center text-xs text-gh-muted flex flex-col items-center space-y-2">
          <Info className="w-5 h-5 text-gh-muted" />
          <p className="font-medium text-gh-fg">No source code dependency graph found</p>
          <p className="text-xs text-gh-muted">This repository contains only non-source documentation/markdown files. Try auditing a codebase with source code (e.g. <span className="font-mono text-gh-fg">.</span> or a Python repository).</p>
        </div>
      ) : (
        <div className="relative">
          <div ref={containerRef} id="cy" className="border border-gh-border rounded-md" />

          {selectedNode && (
            <div className="absolute top-4 right-4 bg-white border border-gh-border p-4 rounded-md shadow-sm max-w-xs text-xs space-y-2">
              <h4 className="font-semibold text-gh-accent truncate">{selectedNode.path}</h4>
              <div className="grid grid-cols-2 gap-2 text-gh-muted pt-1">
                <div>SLOC: <span className="font-medium text-gh-fg">{selectedNode.sloc}</span></div>
                <div>Complexity: <span className="font-medium text-gh-fg">{selectedNode.avg_complexity}</span></div>
                <div>In-Degree: <span className="font-medium text-gh-fg">{selectedNode.in_degree}</span></div>
                <div>Out-Degree: <span className="font-medium text-gh-fg">{selectedNode.out_degree}</span></div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
