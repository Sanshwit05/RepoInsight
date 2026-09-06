import React, { useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import { GraphData } from '../types';
import { Network, ZoomIn, ZoomOut, RotateCcw, Info } from 'lucide-react';

interface Props {
  graphData: GraphData;
}

export const DependencyGraphView: React.FC<Props> = ({ graphData }) => {
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
            'background-color': '#6366f1',
            'label': 'data(label)',
            'color': '#cbd5e1',
            'font-size': '10px',
            'text-valign': 'bottom',
            'text-margin-y': 4,
            'width': 'mapData(in_degree, 0, 5, 20, 50)',
            'height': 'mapData(in_degree, 0, 5, 20, 50)',
            'border-width': 2,
            'border-color': '#818cf8',
          },
        },
        {
          selector: 'node:selected',
          style: {
            'background-color': '#06b6d4',
            'border-color': '#ffffff',
            'border-width': 3,
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 1.5,
            'line-color': '#334155',
            'target-arrow-color': '#64748b',
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
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="flex items-center space-x-2">
          <Network className="w-5 h-5 text-indigo-400" />
          <h2 className="text-base font-bold text-slate-100">Dependency Graph Topology</h2>
        </div>

        <div className="flex items-center space-x-2 text-xs">
          <span className="px-2.5 py-1 rounded-lg bg-slate-800 border border-slate-700 text-slate-300">
            {graphData.total_nodes} nodes
          </span>
          <span className="px-2.5 py-1 rounded-lg bg-slate-800 border border-slate-700 text-slate-300">
            {graphData.total_edges} edges
          </span>
          {graphData.total_nodes > 0 && (
            <div className="flex space-x-1 border border-slate-700 rounded-lg overflow-hidden">
              <button onClick={handleZoomIn} className="p-1.5 hover:bg-slate-800 text-slate-300"><ZoomIn className="w-3.5 h-3.5" /></button>
              <button onClick={handleZoomOut} className="p-1.5 hover:bg-slate-800 text-slate-300"><ZoomOut className="w-3.5 h-3.5" /></button>
              <button onClick={handleReset} className="p-1.5 hover:bg-slate-800 text-slate-300"><RotateCcw className="w-3.5 h-3.5" /></button>
            </div>
          )}
        </div>
      </div>

      {graphData.total_nodes === 0 ? (
        <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-8 text-center text-xs text-slate-400 flex flex-col items-center space-y-2">
          <Info className="w-6 h-6 text-slate-500" />
          <p className="font-semibold text-slate-300">No source code dependency graph found</p>
          <p className="text-[11px] text-slate-500">This repository contains only non-source documentation/markdown files. Try auditing a codebase with source code (e.g. <span className="font-mono text-cyan-400">.</span> or a Python repository).</p>
        </div>
      ) : (
        <div className="relative">
          <div ref={containerRef} id="cy" className="shadow-inner border border-slate-800/80" />

          {selectedNode && (
            <div className="absolute top-4 right-4 bg-slate-900/95 border border-slate-700 p-4 rounded-xl shadow-2xl backdrop-blur max-w-xs text-xs space-y-2">
              <h4 className="font-bold text-indigo-400 truncate">{selectedNode.path}</h4>
              <div className="grid grid-cols-2 gap-2 text-slate-300 pt-1">
                <div>SLOC: <span className="font-semibold text-white">{selectedNode.sloc}</span></div>
                <div>Complexity: <span className="font-semibold text-white">{selectedNode.avg_complexity}</span></div>
                <div>In-Degree: <span className="font-semibold text-white">{selectedNode.in_degree}</span></div>
                <div>Out-Degree: <span className="font-semibold text-white">{selectedNode.out_degree}</span></div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}; 