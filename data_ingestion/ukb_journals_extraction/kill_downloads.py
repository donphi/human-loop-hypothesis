#!/usr/bin/env python3
"""
Kill all running download processes from previous runs.
This script identifies and terminates any Python processes running download_pdfs.py.
It can also optionally kill Docker containers running the download process.
"""

import os
import subprocess
import argparse
import sys
import signal
import time

def find_python_processes():
    """Find all Python processes running download_pdfs.py"""
    try:
        # Use ps command to find Python processes
        cmd = "ps aux | grep 'python.*download_pdfs.py' | grep -v grep"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        processes = []
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) > 1:
                pid = parts[1]
                processes.append((pid, line))
        
        return processes
    except Exception as e:
        print(f"Error finding Python processes: {e}")
        return []

def find_docker_containers():
    """Find all Docker containers running the download process"""
    try:
        # Use docker ps to find containers
        cmd = "docker ps | grep ukb-journals-extraction"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        containers = []
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) > 0:
                container_id = parts[0]
                containers.append((container_id, line))
        
        return containers
    except Exception as e:
        print(f"Error finding Docker containers: {e}")
        return []

def kill_process(pid, process_info, dry_run=False):
    """Kill a process by PID"""
    try:
        if dry_run:
            print(f"Would kill process {pid}: {process_info}")
            return True
        
        print(f"Killing process {pid}: {process_info}")
        os.kill(int(pid), signal.SIGTERM)
        
        # Check if process was killed
        time.sleep(0.5)
        try:
            os.kill(int(pid), 0)  # Signal 0 is used to check if process exists
            print(f"Process {pid} still running, sending SIGKILL...")
            os.kill(int(pid), signal.SIGKILL)
        except OSError:
            # Process no longer exists
            pass
        
        return True
    except Exception as e:
        print(f"Error killing process {pid}: {e}")
        return False

def stop_docker_container(container_id, container_info, dry_run=False):
    """Stop a Docker container by ID"""
    try:
        if dry_run:
            print(f"Would stop Docker container {container_id}: {container_info}")
            return True
        
        print(f"Stopping Docker container {container_id}: {container_info}")
        cmd = f"docker stop {container_id}"
        subprocess.run(cmd, shell=True, check=True)
        return True
    except Exception as e:
        print(f"Error stopping Docker container {container_id}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Kill all running download processes.')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be killed without actually killing')
    parser.add_argument('--include-docker', action='store_true', help='Also kill Docker containers running the download process')
    args = parser.parse_args()
    
    # Find and kill Python processes
    processes = find_python_processes()
    if processes:
        print(f"Found {len(processes)} Python download processes:")
        killed = 0
        for pid, process_info in processes:
            if kill_process(pid, process_info, args.dry_run):
                killed += 1
        
        if args.dry_run:
            print(f"Would kill {killed} Python processes")
        else:
            print(f"Killed {killed} Python processes")
    else:
        print("No Python download processes found")
    
    # Find and stop Docker containers if requested
    if args.include_docker:
        containers = find_docker_containers()
        if containers:
            print(f"\nFound {len(containers)} Docker containers:")
            stopped = 0
            for container_id, container_info in containers:
                if stop_docker_container(container_id, container_info, args.dry_run):
                    stopped += 1
            
            if args.dry_run:
                print(f"Would stop {stopped} Docker containers")
            else:
                print(f"Stopped {stopped} Docker containers")
        else:
            print("\nNo Docker containers found")
    
    print("\nDone!")

if __name__ == "__main__":
    main()