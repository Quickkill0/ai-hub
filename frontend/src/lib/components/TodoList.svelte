<script lang="ts">
	/**
	 * TodoList - Cursor-style task progress display
	 *
	 * Features:
	 * - Compact inline display showing current task
	 * - Expandable to show full task list
	 * - Progress bar and completion count
	 * - Smooth animations for state changes
	 * - Auto-collapses when all tasks complete
	 */
	import type { TodoItem } from '$lib/stores/tabs';

	interface Props {
		todos: TodoItem[];
	}

	let { todos }: Props = $props();

	// Track expanded state
	let isExpanded = $state(false);

	// Compute statistics
	const stats = $derived(() => {
		const total = todos.length;
		const completed = todos.filter(t => t.status === 'completed').length;
		const inProgress = todos.filter(t => t.status === 'in_progress').length;
		const pending = todos.filter(t => t.status === 'pending').length;
		const percent = total > 0 ? Math.round((completed / total) * 100) : 0;
		return { total, completed, inProgress, pending, percent };
	});

	// Get the currently active task (first in_progress, or first pending)
	const activeTask = $derived(() => {
		const inProgressTask = todos.find(t => t.status === 'in_progress');
		if (inProgressTask) return inProgressTask;
		return todos.find(t => t.status === 'pending');
	});

	// Check if all tasks are completed
	const allCompleted = $derived(() => {
		return todos.length > 0 && todos.every(t => t.status === 'completed');
	});

	// Get status icon and color for a todo
	function getStatusConfig(status: string) {
		switch (status) {
			case 'completed':
				return { icon: 'check', color: 'text-green-500', bgColor: 'bg-green-500/10' };
			case 'in_progress':
				return { icon: 'spinner', color: 'text-primary', bgColor: 'bg-primary/10' };
			default:
				return { icon: 'circle', color: 'text-muted-foreground', bgColor: 'bg-muted/30' };
		}
	}
</script>

{#if todos.length > 0}
	<div class="todo-list w-full border border-border rounded-xl overflow-hidden shadow-sm bg-card/50 backdrop-blur-sm transition-all duration-300" class:todo-complete={allCompleted()}>
		<!-- Compact Header - Always Visible -->
		<button
			onclick={() => isExpanded = !isExpanded}
			class="w-full px-4 py-3 flex items-center gap-3 hover:bg-muted/30 transition-colors cursor-pointer text-left"
		>
			<!-- Status Icon -->
			{#if allCompleted()}
				<div class="w-6 h-6 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
					<svg class="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
						<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
					</svg>
				</div>
			{:else if stats().inProgress > 0}
				<div class="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
					<svg class="w-4 h-4 text-primary animate-spin" fill="none" viewBox="0 0 24 24">
						<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
						<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
					</svg>
				</div>
			{:else}
				<div class="w-6 h-6 rounded-full bg-muted/50 flex items-center justify-center flex-shrink-0">
					<svg class="w-4 h-4 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
					</svg>
				</div>
			{/if}

			<!-- Task Info -->
			<div class="flex-1 min-w-0">
				{#if allCompleted()}
					<div class="flex items-center gap-2">
						<span class="text-sm font-medium text-green-500">All tasks completed</span>
						<span class="text-xs text-muted-foreground">({stats().total} tasks)</span>
					</div>
				{:else if activeTask()}
					<div class="flex items-center gap-2">
						<span class="text-sm font-medium text-foreground truncate">
							{activeTask()?.status === 'in_progress' ? activeTask()?.activeForm : activeTask()?.content}
						</span>
					</div>
					<div class="flex items-center gap-2 mt-0.5">
						<span class="text-xs text-muted-foreground">{stats().completed} of {stats().total} completed</span>
					</div>
				{:else}
					<span class="text-sm text-muted-foreground">{stats().total} pending tasks</span>
				{/if}
			</div>

			<!-- Progress Ring (Mobile) / Bar (Desktop) -->
			<div class="flex items-center gap-3">
				<!-- Progress Bar (Desktop) -->
				<div class="hidden sm:flex items-center gap-2">
					<div class="w-20 h-1.5 bg-muted rounded-full overflow-hidden">
						<div
							class="h-full transition-all duration-500 ease-out rounded-full"
							class:bg-green-500={allCompleted()}
							class:bg-primary={!allCompleted()}
							style="width: {stats().percent}%"
						></div>
					</div>
					<span class="text-xs text-muted-foreground tabular-nums w-8">{stats().percent}%</span>
				</div>

				<!-- Expand Chevron -->
				<svg
					class="w-4 h-4 text-muted-foreground transition-transform duration-200 flex-shrink-0"
					class:rotate-180={isExpanded}
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
				</svg>
			</div>
		</button>

		<!-- Mobile Progress Bar -->
		{#if !allCompleted()}
			<div class="sm:hidden px-4 pb-3 -mt-1">
				<div class="flex items-center gap-2">
					<div class="flex-1 h-1 bg-muted rounded-full overflow-hidden">
						<div
							class="h-full bg-primary transition-all duration-500 ease-out rounded-full"
							style="width: {stats().percent}%"
						></div>
					</div>
					<span class="text-xs text-muted-foreground tabular-nums">{stats().percent}%</span>
				</div>
			</div>
		{/if}

		<!-- Expanded Task List -->
		{#if isExpanded}
			<div class="border-t border-border bg-card/30">
				<div class="max-h-64 overflow-y-auto">
					{#each todos as todo, index (index)}
						{@const config = getStatusConfig(todo.status)}
						<div
							class="px-4 py-2.5 flex items-start gap-3 border-b border-border/50 last:border-b-0 transition-colors duration-200 {todo.status === 'in_progress' ? 'bg-primary/5' : ''}"
						>
							<!-- Status Icon -->
							<div class="w-5 h-5 mt-0.5 rounded-full {config.bgColor} flex items-center justify-center flex-shrink-0">
								{#if config.icon === 'check'}
									<svg class="w-3 h-3 {config.color}" fill="currentColor" viewBox="0 0 20 20">
										<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
									</svg>
								{:else if config.icon === 'spinner'}
									<svg class="w-3 h-3 {config.color} animate-spin" fill="none" viewBox="0 0 24 24">
										<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
										<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
									</svg>
								{:else}
									<div class="w-2 h-2 rounded-full bg-muted-foreground/40"></div>
								{/if}
							</div>

							<!-- Task Content -->
							<div class="flex-1 min-w-0">
								<p
									class="text-sm transition-colors duration-200"
									class:text-foreground={todo.status !== 'completed'}
									class:text-muted-foreground={todo.status === 'completed'}
									class:line-through={todo.status === 'completed'}
								>
									{todo.status === 'in_progress' ? todo.activeForm : todo.content}
								</p>
							</div>

							<!-- Status Badge -->
							{#if todo.status === 'in_progress'}
								<span class="text-xs text-primary font-medium px-2 py-0.5 bg-primary/10 rounded-full flex-shrink-0">
									Active
								</span>
							{/if}
						</div>
					{/each}
				</div>
			</div>
		{/if}
	</div>
{/if}

<style>
	.todo-list {
		animation: slideIn 0.3s ease-out;
	}

	.todo-complete {
		border-color: rgb(34 197 94 / 0.3);
	}

	@keyframes slideIn {
		from {
			opacity: 0;
			transform: translateY(8px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}
</style>
