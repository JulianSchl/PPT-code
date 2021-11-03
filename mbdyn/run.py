#import packages

class MbdynAdapter:
	#initialize values
	
	def run(self):
		dt = interface.initialize()
		self.mbdyn.initialize(case=self.mbdyn_prep.name)

		while interface.is_coupling_ongoing():
			if interface.is_action_required(precice.action_write_iteration_checkpoint()):
				print("DUMMY: Writing iteration checkpoint")
				interface.mark_action_fulfilled(precice.action_write_iteration_checkpoint())

			for i in range(self.patches):
				if interface.is_read_data_available():
					self.read_data.append(interface.read_block_vector_data(self.read_data_id[i], self.vertex_ids[i]))
				elif float(self.current_time_step) == float(decimal.Decimal(str(dt))):
					self.read_data.append(self.vertices[i]*0)
				else:
					exit("no data provided!")
				self.force_tensor.append(np.split(self.read_data[i],2)[0]*0) # prepare force_tensor for entries
				self.force_tensor[i] = np.concatenate((self.force_tensor[i],self.force_tensor[i][:2,:]*0)) # prepare force_tensor for entries, add empty anchor & ground force node
				for k,j in enumerate(np.split(self.read_data[i],2)):
					self.force_tensor[i] += np.concatenate((j,j[:2,:]*0)) # fill values into force_tensor, add empty anchor & ground force node
					
			self.mbdyn.set_forces(np.vstack(self.force_tensor))
			if self.mbdyn.solve(False):
				self.module_logger.debug('Something went wrong!')
				#MBDyn diverges
				break
			
			##############################
			### evaluate OpenFOAM data ###
			##############################
			
			#############################
			### evaluate preCICE data ###
			#############################
			
			if interface.is_write_data_required(dt):
				for i in range(self.patches):
					interface.write_block_vector_data(self.write_data_id[i], self.vertex_ids[i], self.write_data[i])
			
			print("DUMMY: Advancing in time")
			dt = interface.advance(dt)
			self.current_time_step += decimal.Decimal(str(dt))
			if interface.is_action_required(precice.action_read_iteration_checkpoint()):
				print("DUMMY: Reading iteration checkpoint")
				interface.mark_action_fulfilled(
				    precice.action_read_iteration_checkpoint())
				exit("ERROR MBDyn got no values")
			else:
				
				#MBDyn advance
				if self.mbdyn.solve(True):
					print("diverged")
					break

			self.iteration += 1
		print("preCICE finalizing")
		interface.finalize()
		print("DUMMY: Closing python solver dummy...")
